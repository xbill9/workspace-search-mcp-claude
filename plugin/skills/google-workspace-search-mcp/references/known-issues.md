# Known issues: sign-in

Two limits on how long Claude Code stays signed in to Google's Workspace MCP
servers. Both come from how Claude Code asks Google for a sign-in and how
Google scopes a grant, so they apply to `workspace-universal` as they do to the
per-product servers. The measurements are from the per-product servers
(Gmail, Drive, People) with Claude Code 2.1.289 to 2.1.292 on 2026-10-04 and
2026-10-06; the full investigation is the article
`docs/source/devto-debugging-claude-code-and-google-mcp-quirks.md`
([dev.to](https://dev.to/gde/debugging-claude-code-and-google-mcp-quirks-8bd)).
`workspace-universal` uses the same authorization server, `accounts.google.com`
(its protected resource metadata, checked 2026-10-08).

Confirmed on `workspace-universal` on 2026-10-08 with Claude Code 2.1.294:
the authorization URL carried the four pinned scopes and no `access_type`, and
after sign-in `mcp_status.sh --verify` showed `valid`, 60 minutes left,
refresh `no`.

## 1. Sign-ins last about an hour

Google's access tokens last one hour for every app. A one-hour *sign-in* means
Claude Code holds no refresh token to renew it.

- Claude Code requests a refresh token the MCP way: it adds the
  `offline_access` scope, and only when the authorization server lists that
  scope in `scopes_supported`. `accounts.google.com` lists `openid`, `email`
  and `profile` (OpenID configuration, re-checked 2026-10-08).
- Google rejects `offline_access` outright: a sign-in request with
  `gmail.readonly offline_access` returns `invalid_scope`
  (`invalid=[offline_access]`). So **never add `offline_access` to the pinned
  scopes** in `claude_setup.sh`: every sign-in would fail.
  `tests/test_consistency.py` checks it is absent.
- Google issues refresh tokens through its own parameter,
  `access_type=offline`. The authorization URL Claude Code builds carries
  `response_type`, `client_id`, PKCE, `redirect_uri`, `state`, `scope` and
  `resource`, and no `access_type`.
- Claude Code's `oauth` server config accepts `clientId`, `callbackPort`,
  `scopes` and `authServerMetadataUrl`; none adds an authorization parameter.
- The same sign-in made outside Claude Code (`docs/article/oauth_probe.py`)
  with `access_type=offline&prompt=consent` returned a refresh token, which
  returned a new access token without a browser. The missing parameter is the
  whole gap.

## 2. Signing in again revokes every token on the OAuth client

Starting a new sign-in while the token still works makes Claude Code revoke the
old token at Google's revocation endpoint, and Google revokes the whole grant
for that OAuth client: every access token and refresh token it issued to that
user, at once.

| Step (per-product servers, 2026-10-06) | Result (Google tokeninfo) |
|---|---|
| Revoke one People access token | Gmail and both People tokens rejected |
| Fresh Gmail and Drive; revoke the Drive access token | Gmail rejected too |
| Gmail and Drive signed in through Claude Code; `claude mcp login drive` started | Gmail `revoked` with 58 minutes left |
| A Gmail refresh token issued before these revocations | `Token has been expired or revoked` |

With one server this is simpler than with eight, but the grant is per OAuth
client, not per server:

- If `workspace-universal` uses the same OAuth client as the per-product
  Workspace MCP servers (the default: both read `~/client_id.txt`), signing it
  in again signs all of them out, and the reverse.
- Other MCP clients (Codex CLI, Antigravity CLI, Gemini CLI) on the same OAuth
  client share the grant too; revoking one Codex token invalidated
  Antigravity's refresh token (`clients.md`).
- A sign-in on its own revokes nothing; the revoke of the old token does. An
  `expired` or `revoked` token can be replaced without touching anything else.

### Why it is easy to miss

- `claude mcp list` keeps showing `✔ Connected`: the server answers
  `tools/list` without a token.
- The stored expiry still shows minutes left.
- In a session the tool is absent, so Claude says it has no search tool rather
  than reporting an authentication error. With `--debug`, the log shows
  `Failed to fetch tools: Unauthorized`.

`mcp_status.sh --verify` asks Google and reports `revoked`. `mcp_test.sh`
reports `FAIL` (direct call) and `NOT CALLED` (through Claude Code).

## Working with these limits

- Before a working session, `mcp_status.sh --verify`. Sign in only when it
  says `expired`, `revoked` or `none`.
- Never sign in again while the token is `valid`. `mcp_login.sh start` revokes
  the current token immediately, whether or not the new sign-in finishes.
- To keep the search server's sign-ins apart from the per-product servers,
  give it its own Web application client (same project, same consent screen):
  `CLIENT_ID=… CLIENT_SECRET=… ./claude_setup.sh`. Not measured here yet.

## Getting past the hour

These keep a refresh token outside Claude Code; the article above has the
tradeoffs. Both helpers know `workspace-universal`.

- **`headersHelper`** with `docs/article/token_header.py`, after
  `oauth_probe.py signin workspace-universal workspace-universal access_type=offline prompt=consent`.
  The helper must refresh on every call: Claude Code calls it only at connect.
- **A local proxy**, `docs/article/token_proxy.py`, with the server registered
  as `http://127.0.0.1:8790/workspace-universal/mcp/v1`. It refreshes and
  retries on Google's `401`.

Measured with the Gmail server (2026-10-06, Claude Code 2.1.292); not yet run
against `workspace-universal`.

## Where the fix belongs

- **Google's authorization server**: accepting `offline_access` and listing it
  in `scopes_supported` would make Claude Code's existing code request it, and
  every client that follows the MCP specification.
- **Claude Code**: an `oauth` field for extra authorization parameters would
  let `access_type=offline` through without a Google-specific case.
