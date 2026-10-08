# Using the server from more than one MCP client

Google's guide documents Antigravity and Claude (custom connector). Claude Code
is scripted here; Gemini CLI has a checked-in config. The per-client sign-in
behaviour below was measured against the per-product Gmail server on
2026-10-06 (`docs/article/evidence/other-clients-*.txt`); the clients sign in to
every Google MCP server the same way.

## Configuration per client

**Claude Code.** `claude_setup.sh`: `claude mcp add-json --client-secret`, the
secret in Claude Code's credential store, scopes pinned, redirect
`http://localhost:8765/callback`.

**Claude.ai and Claude Desktop** (Pro, Max, Team, Enterprise): **Settings →
Connectors → Add custom connector**:

- Name `Universal Search MCP Server`
- URL `https://workspacemcp.googleapis.com/mcp/v1`
- OAuth client ID and secret under **Advanced settings**
- Scopes: `gmail.readonly`, `drive.readonly`, `calendar.readonly`,
  `chat.messages.readonly` (full URLs in `server.md`)

The OAuth client needs `https://claude.ai/api/mcp/auth_callback`.

**Antigravity** (2.0, IDE, CLI): `~/.gemini/config/mcp_config.json`:

```json
{
  "mcpServers": {
    "workspace-universal": {
      "serverUrl": "https://workspacemcp.googleapis.com/mcp/v1",
      "oauth": { "clientId": "OAUTH_CLIENT_ID", "clientSecret": "OAUTH_CLIENT_SECRET" }
    }
  }
}
```

Redirect URI `https://antigravity.google/oauth-callback`. Sign in from `/mcp`
→ `workspace-universal` → Authenticate, then paste the code the page shows.

**Gemini CLI**: `.gemini/settings.json` in this repo, with `CLIENT_ID` and
`CLIENT_SECRET` from `source ./save_oauth.sh`; `/mcp auth workspace-universal`.

## How each client signs in (measured on the Gmail server)

| | Claude Code | Codex CLI | Antigravity CLI |
|---|---|---|---|
| Client secret in config | no (credential store) | yes, `config.toml` | yes, `mcp_config.json` |
| Scopes requested | pinned | `--scopes` on login | every scope in the server's metadata |
| `access_type=offline` | no | no | yes, with `prompt=consent` |
| Sign-in lasts | 1 hour | 1 hour | renews without a browser |
| Tokens stored in | credential store | keyring or `$CODEX_HOME/.credentials.json` | `~/.gemini/antigravity-cli/mcp_oauth_tokens.json`, mode 644, with the secret |

Antigravity requests every scope the server lists. For `workspace-universal`
that is nine, including `https://mail.google.com/` ("Read, compose, send, and
permanently delete all your email") and full `drive`, where the guide's four
read-only scopes would do. Every scope it asks for must be on the consent
screen, or the sign-in fails.

## One OAuth client, one grant

To Google one OAuth client is one app with one grant per user, and every
client's sign-in adds to it. Revoking one Codex token also invalidated
Antigravity's access and refresh tokens. Claude Code revokes the old token on
every re-sign-in, so signing in again in Claude Code ends every other client's
sign-in on the same OAuth client. The grant is also cumulative: after
Antigravity's sign-in, the app holds full Gmail access whichever client asked.

A separate Web application client per MCP client (same project, same consent
screen) keeps grants, scope sets and revocations apart, at the cost of one
console step and one pair of `client_id`/`client_secret` files per client.
