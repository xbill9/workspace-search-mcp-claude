# Workspace Search MCP

Scripts, a Claude Code skill and tests that connect **Claude Code** (and Gemini CLI) to Google's [Universal Search MCP server for Workspace](https://developers.google.com/workspace/guides/universal-search-mcp): one remote MCP server, one tool, `search_corpus`, that searches Gmail, Drive, Calendar and Chat in a single call.

The Universal Search MCP server is in Developer Preview. Join the [Google Workspace Developer Preview Program](https://developers.google.com/workspace/preview) first.

This repository is the search counterpart of [workspace-mcp-claude](https://github.com/xbill9/workspace-mcp-claude), which sets up the eight per-product Workspace MCP servers. The setup, sign-in handling and known issues carry over; the companion articles are in [`docs/source/`](docs/source/).

## Install as a Claude Code plugin

```
/plugin marketplace add xbill9/workspace-search-mcp-claude
/plugin install google-workspace-search-mcp@workspace-search-mcp-claude
```

Then ask Claude Code something like *"set up Workspace search"* or *"search my Workspace for the Q3 plan"*. The skill lives in `plugin/skills/google-workspace-search-mcp/`: `SKILL.md`, the scripts in `scripts/`, and `references/` for the console steps, the tool schema, scopes and quirks. The scripts at the repo root are wrappers around the skill's copies, so `./bootstrap.sh` and the rest work from a clone too.

## The server

| | |
|---|---|
| Name in Claude Code | `workspace-universal` |
| URL | `https://workspacemcp.googleapis.com/mcp/v1` |
| Tool | `search_corpus(query, pageSize?, pageToken?)`, read-only |
| Searches | Gmail threads, Drive files, Calendar events, Chat messages |
| MCP versions | 2024-11-05 to 2026-07-28 (`server/discover`); `initialize` negotiates 2025-11-25 |
| Auth | OAuth 2.0, Web application client |

From `./mcp_probe.sh` on 2026-10-08. Each result item holds one of `gmailResult` (a thread with its messages), `driveResult`, `calendarResult` or `chatResult` (a group of messages), each with a `viewUrl`. Full schema: [`server.md`](plugin/skills/google-workspace-search-mcp/references/server.md).

### OAuth scopes

One scope per corpus. The server searches only the corpora whose scope the sign-in granted.

| Corpus | Scope (`https://www.googleapis.com/auth/…`) |
|---|---|
| gmail | `gmail.readonly` |
| drive | `drive.readonly` |
| calendar | `calendar.readonly` |
| chat | `chat.messages.readonly` |

`claude_setup.sh` pins all four. `CORPORA="drive calendar" ./claude_setup.sh` pins a subset. `./mcp_status.sh --verify` reads the granted scopes back from Google and names the corpora they cover.

## Known issues: sign-in

Both come from how Claude Code asks Google for a sign-in, so they apply here as they do to the per-product servers. Details, evidence and workarounds: [`known-issues.md`](plugin/skills/google-workspace-search-mcp/references/known-issues.md) and the article [Debugging Claude Code and Google MCP Quirks](https://dev.to/gde/debugging-claude-code-and-google-mcp-quirks-8bd).

- ⚠️ **Sign-ins last about an hour.** Claude Code asks for a refresh token with the `offline_access` scope, and only when the authorization server lists it. Google lists it nowhere, rejects it as `invalid_scope`, and issues refresh tokens only through `access_type=offline`, which Claude Code does not send.
- ⚠️ **Signing in again while the token works revokes every token on the OAuth client.** Google revokes the whole grant. If `workspace-universal` shares its OAuth client with the per-product Workspace servers or with other MCP clients, they are signed out too. `claude mcp list` keeps showing `✔ Connected`.

To work with them:

- 🟢 `./mcp_status.sh --verify` before a session; sign in only when it says `expired`, `revoked` or `none`.
- 🟢 A separate OAuth client for search keeps its sign-ins apart from the per-product servers.
- 🟢 `docs/article/token_header.py` (headersHelper) and `docs/article/token_proxy.py` (local proxy) hold a refresh token outside Claude Code; both know `workspace-universal`.

## Quick start: `bootstrap.sh`

Once the console steps (2–4 below) are done:

```bash
./bootstrap.sh                          # newest ~/Downloads/client_secret_*.json
./bootstrap.sh path/to/client.json      # or a specific client file
```

It enables the five APIs, installs the OAuth client from the file the console's **Download JSON** button saves (to `~/client_id.txt` and `~/client_secret.txt`, mode 600, never printed), runs `claude_setup.sh`, signs in with `claude mcp login workspace-universal`, and lists the result. `--no-apis` skips the gcloud step; `--no-login` skips sign-in.

## Getting started with Claude Code

1. `./init.sh` enables `gmail`, `drive`, `calendar-json`, `chat` and `workspacemcp` on the project in `~/project_id.txt`.
2. OAuth consent screen: **Google Auth Platform → Branding → Get Started**, Audience **Internal** (or External plus yourself as a test user), then add the four scopes above under **Data Access**. A consent screen from the per-product setup usually needs `calendar.readonly` and `chat.messages.readonly` added.
3. OAuth client: **Google Auth Platform → Clients → Create Client**, type **Web application**, Authorized redirect URIs:
   - `http://localhost:8765/callback` (Claude Code, matches `CALLBACK_PORT`)
   - `https://claude.ai/api/mcp/auth_callback` (only for claude.ai / Claude Desktop connectors)
   - `https://antigravity.google/oauth-callback` (only for Antigravity)
4. `source ./save_oauth.sh` and enter the client ID and secret.
5. `./claude_setup.sh`
6. Sign in with `/mcp` inside Claude Code, or `claude mcp login workspace-universal`. Over SSH, add `--no-browser`.
7. `./mcp_status.sh --verify` and `./mcp_test.sh`, then restart Claude Code and ask *"Find anything related to Project X across my email, docs, and chat messages."*

The Chat app configuration the per-product Chat server needs is not part of Google's guide for this server.

## Scripts

| Script | Does |
|---|---|
| `init.sh` | enables the five APIs, writes `.env`, checks ADC |
| `set_env.sh`, `set_adc.sh` | refresh `.env`; check gcloud and ADC (`source ./set_adc.sh`) |
| `save_oauth.sh` | prompts for and exports `PROJECT_ID`, `CLIENT_ID`, `CLIENT_SECRET` (`source` it) |
| `bootstrap.sh` | APIs, OAuth client from its JSON, registration, sign-in |
| `claude_setup.sh` | registers `workspace-universal` and `workspace-developer` with `claude mcp add-json --client-secret`; the secret goes to Claude Code's credential store |
| `mcp_login.sh` | sign-in without a terminal: `start` prints the Google URL, `check` confirms |
| `mcp_status.sh` | registered, token held, minutes left, refresh token; `--verify` asks Google and lists covered corpora |
| `mcp_search.sh` | calls `search_corpus` directly with the stored token, prints the exact count per corpus, then one line per result; `--json` for scripts |
| `mcp_test.sh` | read-only test: direct call, then a headless Claude Code session graded from its tool results |
| `mcp_probe.sh` | no credentials: MCP versions, tool schema, resource scopes by corpus |
| `mcp_setup.sh` | prints the sign-in commands for Claude Code and Gemini CLI |

`claude_setup.sh` variables:

| Variable | Default | Meaning |
|---|---|---|
| `CALLBACK_PORT` | `8765` | Port in the redirect URI `http://localhost:PORT/callback` |
| `MCP_SCOPE` | `user` | `user` (all projects), `local` (this directory, private), or `project` (writes `.mcp.json`, no secret) |
| `CORPORA` | `gmail drive calendar chat` | products whose scope is pinned |

Every count the scripts print is computed in `scripts/wsearch.py`, never left to the model: `mcp_test.sh` grades Claude Code's session from the tool calls and tool results in its event stream, and counts the results per corpus from the tool result itself.

```
$ ./mcp_search.sh "meeting" --page-size 10
query: 'meeting'  arguments sent: {"query": "meeting", "pageSize": 10}

corpus    results
gmail           2
drive           3
calendar        1
chat            1
total           7
```

(Output format; the numbers here are the test fixture.)

## Tests

```bash
tests/run.sh          # offline: syntax, shellcheck, unit, consistency, script behaviour, plugin validate
tests/run.sh --live   # adds the no-credential probe and, when signed in, mcp_test.sh
```

- `tests/test_wsearch.py`: scope-to-corpus mapping (including the guide's partial-grant example), token selection from Claude Code's store, JSON and SSE response parsing, per-corpus counting, and grading of PASS, FAIL and NOT CALLED sessions from fixtures.
- `tests/test_consistency.py`: the server name, URL, scopes and APIs agree across the scripts, `.gemini/settings.json`, the docs and the manifests; `offline_access` stays out of the pinned scopes.
- `tests/test_scripts.sh`: `claude_setup.sh` against a stub `claude` (the secret reaches Claude Code only through the environment, never argv or output; `CORPORA`, `MCP_SCOPE` and `CALLBACK_PORT` are honoured), and argument handling in `mcp_login.sh`, `mcp_search.sh` and the grader.

## Other clients

- **claude.ai and Claude Desktop**: **Settings → Connectors → Add custom connector**, name `Universal Search MCP Server`, URL above, client ID and secret under **Advanced settings**, the four scopes. Needs the `https://claude.ai/api/mcp/auth_callback` redirect URI.
- **Antigravity**: `workspace-universal` in `~/.gemini/config/mcp_config.json` with `serverUrl` and `oauth.clientId`/`clientSecret`. It requests all nine scopes the server lists, including full Gmail access.
- **Gemini CLI**: `.gemini/settings.json` here, with `CLIENT_ID`/`CLIENT_SECRET` from `save_oauth.sh`; `/mcp auth workspace-universal`.

Details and the shared-grant caveat: [`clients.md`](plugin/skills/google-workspace-search-mcp/references/clients.md).

## References

- [Universal Search MCP Server for Workspace](https://developers.google.com/workspace/guides/universal-search-mcp)
- [Configure the Google Workspace MCP servers](https://developers.google.com/workspace/guides/configure-mcp-servers)
- [MCP Configuration for Google Workspace with Claude Code](https://dev.to/gde/mcp-configuration-for-google-workspace-with-claude-code-11om)
- [Debugging Claude Code and Google MCP Quirks](https://dev.to/gde/debugging-claude-code-and-google-mcp-quirks-8bd)
- [Claude Code MCP](https://code.claude.com/docs/en/mcp)
