# Quirks

Behaviour of the Universal Search MCP server and of Claude Code around it.
Server entries are from `mcp_probe.sh` and direct requests on 2026-10-08; the
sign-in, Claude Code and console entries were measured on the per-product
Workspace MCP servers (2026-10-04 to 2026-10-06, Claude Code 2.1.289–2.1.292)
and concern the same sign-in pages, client and console. The two sign-in limits
with lasting impact are in `known-issues.md`.

## 1. The server

- **`tools/list` answers without a token**, so `claude mcp list` shows
  `✔ Connected` before any sign-in. Only a tool call needs one.
- **An unauthenticated call is refused inside the JSON-RPC result.**
  `tools/call` without a token returns HTTP 403 with
  `"isError": true` and "Method doesn't allow unregistered callers (callers
  without established identity)". Read it as "not signed in".
- **It speaks MCP 2026-07-28.** `server/discover` needs the
  `Mcp-Method: server/discover` header and lists 2024-11-05 through
  2026-07-28. A legacy `initialize` negotiates 2025-11-25.
- **Two server names.** `server/discover` reports `workspacemcp`; `initialize`
  reports `StatelessServer`. Its `instructions` mention Drive, Gmail and
  Calendar; the tool covers Chat as well.
- **`pageToken` is in the schema, pagination is not.** The tool description
  says cross-corpus search does not paginate, while `inputSchema` has
  `pageToken` and `outputSchema` has `nextPageToken`. `mcp_search.sh` reports
  whether a `nextPageToken` came back.
- **One Gmail result is a thread.** A `gmailResult` holds a thread with its
  messages, and a `chatResult` a group of messages. Item count and message
  count differ; `wsearch.py` reports both.
- **Gmail attachments appear in the snippet**, not as a field.
- **The tool description steers the model.** It says to call `search_corpus`
  first for any question that names no product, and to use per-product tools
  only when it returns nothing. With the per-product servers also registered,
  expect Claude to reach for `search_corpus` first.
- **The protected resource metadata offers broad scopes**, including
  `https://mail.google.com/` and full `drive`. Pinning `oauth.scopes` in
  `claude_setup.sh` keeps Claude Code from requesting them.

## 2. Google sign-in pages

- **The account chooser ignores the first interaction after it loads.** Click
  the account and press Enter; if "Choose an account" is still showing, do it
  once more.
- **The Allow button moves** with the number of permissions listed; find it by
  its label rather than by coordinates.
- **A previously approved app goes straight to the permissions page**; Allow is
  needed every time.
- **Partial grants narrow the search.** Google's guide says the server
  searches only the corpora whose scope was granted, so unticking a permission
  on the consent page leaves that corpus out. `mcp_status.sh --verify` lists
  the corpora the granted scopes cover.

## 3. Claude Code

- **`claude mcp login` needs a terminal.** From a non-interactive shell it
  stops with "stdin isn't a terminal". `mcp_login.sh` runs it under `script`
  with `BROWSER=/bin/true` and prints the sign-in URL instead.
- **Starting a login revokes the current token** at once, whether or not the
  login finishes (`known-issues.md` §2).
- **Revoked tokens look healthy**: `✔ Connected`, minutes left on the expiry,
  and no tool in the session. `mcp_status.sh --verify` is the direct check.
- **New servers and new sign-ins load in the next session.**
- **`local` scope belongs to a directory.** A server added with `local` scope
  exists only for the working directory at the time of `claude mcp add`.
  Scripts that register servers must not `cd` first.
- **The client secret is set only when a server is added**
  (`--client-secret` with `MCP_CLIENT_SECRET`). Changing it means removing and
  adding the server again, which `claude_setup.sh` does.
- **MCP tools in a headless session are deferred** and reached through
  ToolSearch; the `init` event's `tools` list may not show them.
- **Auto mode blocks credential handling.** Reading the client secret from the
  console or the downloaded file is refused; the user downloads it and
  `bootstrap.sh` installs it without printing it.

## 4. Google Cloud console

- **One URL enables all five APIs** (`console-setup.md` §1).
- **The client secret is shown once.** Later visits say "Viewing and
  downloading client secrets is no longer available"; **Add secret** creates a
  new one with a download button.
- **Shadow DOM hides most form fields** from accessibility-tree tools; a
  JavaScript walker over `shadowRoot`s finds them.
- **Typing without a focused field fires console keyboard shortcuts.** Use
  `form_input` with element refs.
- **Unused OAuth clients are deleted** after six months.

## 5. Environment

- **gcloud cannot re-authenticate without a terminal**: the user runs
  `gcloud auth login`, or the APIs are enabled in the console.
- **ChromeOS keeps browser downloads outside Linux** until Downloads is shared
  with Linux (`/mnt/chromeos/MyFiles/Downloads`).
