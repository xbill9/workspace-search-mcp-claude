# The Universal Search MCP server

One Google-hosted MCP server searches Gmail, Drive, Calendar and Chat with a
single tool. Developer Preview: the account must be in the
[Google Workspace Developer Preview Program](https://developers.google.com/workspace/preview).
Source: [Google's guide](https://developers.google.com/workspace/guides/universal-search-mcp)
and `mcp_probe.sh` on 2026-10-08 (copies in `docs/source/`).

| | |
|---|---|
| Name in Claude Code | `workspace-universal` (the name Google's guide uses) |
| URL | `https://workspacemcp.googleapis.com/mcp/v1` |
| Transport | Streamable HTTP |
| Auth | OAuth 2.0, Web application client, `accounts.google.com` |
| MCP versions | `server/discover` lists 2024-11-05, 2025-03-26, 2025-06-18, 2025-11-25, 2026-07-28; legacy `initialize` negotiates 2025-11-25 |
| Tools | 1: `search_corpus` |

## APIs to enable

```bash
gcloud services enable gmail.googleapis.com drive.googleapis.com \
    calendar-json.googleapis.com chat.googleapis.com \
    workspacemcp.googleapis.com --project=PROJECT_ID
```

`workspacemcp.googleapis.com` is the Google Workspace MCP API. The product APIs
are needed for each corpus searched. Unlike the per-product Chat MCP server,
Google's guide asks for no Chat app configuration.

## Scopes

Each scope turns on one corpus. The server searches only the corpora whose
scope the sign-in granted, and returns no results from the others.

| Corpus | Scope pinned by `claude_setup.sh` (`https://www.googleapis.com/auth/…`) | Broader scopes the server also accepts |
|---|---|---|
| gmail | `gmail.readonly` | `gmail.modify`, `https://mail.google.com/` |
| drive | `drive.readonly` | `drive` |
| calendar | `calendar.readonly` | `calendar` |
| chat | `chat.messages.readonly` | `chat.messages` |

The pinned four are the read-only scopes in Google's guide. The broader ones are
listed in the server's protected resource metadata
(`/.well-known/oauth-protected-resource/mcp/v1`, 9 scopes); pinning keeps
Claude Code from requesting them. `CORPORA="drive calendar" ./claude_setup.sh`
pins a subset. `mcp_status.sh --verify` reads the granted scopes back from
Google and names the corpora they cover.

## `search_corpus`

Annotations: `readOnlyHint: true`, `destructiveHint: false`,
`idempotentHint: true`, title "Search Workspace Corpora".

Arguments:

| Argument | Type | |
|---|---|---|
| `query` | string | required: the user's raw query |
| `pageSize` | int32 | in the schema; ignored (30 items whatever the value, measured 2026-10-08) |
| `pageToken` | string | in the schema; the tool description says cross-corpus search does not paginate, and no response carried a `nextPageToken` |

Result (`structuredContent`): `items[]`, each item holding exactly one of:

| Key | Fields |
|---|---|
| `gmailResult` | `thread { threadId, messages[] { messageId, subject, sender, recipients, ccRecipients, snippet, viewUrl } }` |
| `driveResult` | `itemId, title, mimeType, contentSnippet, viewUrl` |
| `calendarResult` | `eventId, calendarId, title, description, location, start, end, viewUrl` (`start`/`end`: `date` or `dateTime` + `timeZone`) |
| `chatResult` | `messages[] { id { messageId, threadId }, sender, plaintextBody, createTime, attachments, reactionSummaries, threadedReply, viewUrl }` |

plus an optional `nextPageToken`. Gmail attachments are described inside the
message `snippet`, not in a separate field.

A broad query returns about 30 items, roughly 52 KB, and the split across
corpora varies between identical calls. In Claude Code 2.1.294 that is over the
MCP output limit, so the model receives a saved-to-file notice instead of the
result (`quirks.md` §3).

The tool description tells the model to call `search_corpus` first when a
question names no product, and to fall back to per-product tools
(`search_threads`, `list_events`, `search_files`) only when it returns nothing.

## Counting results

`mcp_search.sh <query>` and `mcp_test.sh` count results per corpus in code
(`wsearch.py count_by_corpus`): one Gmail thread or one Chat conversation is one
result, and the messages inside them are counted separately. Quote those
numbers; do not count `items` by reading them.
