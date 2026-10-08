---
title: "Universal Search MCP for Google Workspace with Claude Code"
published: false
description: "Connect Claude Code to Google's Universal Search MCP server, one search_corpus tool across Gmail, Drive, Calendar and Chat, packaged as a Claude Code skill with tests, and what the live results mean for using it."
tags: claudecode, mcp, googleworkspace, googleoauth
cover_image: https://raw.githubusercontent.com/xbill9/workspace-search-mcp-claude/main/docs/search-article/devto-cover.09d61064.jpg
---

This article provides a step by step configuration guide for Google's Universal Search MCP server for Workspace with Claude Code. The setup is packaged as a Claude Code skill and plugin with an offline test suite, so Claude Code can enable the APIs, register the server, sign in, search, and test the result.

https://github.com/xbill9/workspace-search-mcp-claude

**One tool, `search_corpus`, searches Gmail, Drive, Calendar and Chat in a single call, and it passes a live test from Claude Code. Every broad search returns about 30 results whatever `pageSize` says, which is more than Claude Code passes to the model, so counts come from a script and the model reads a saved file.**

---

#### Didn't You Already Do This?

Yes! The companion article connects Claude Code to the eight per-product Workspace MCP servers, and a second one works through why every sign-in lasts an hour:

[MCP Configuration for Google Workspace with Claude Code](https://dev.to/gde/mcp-configuration-for-google-workspace-with-claude-code-11om)

[Debugging Claude Code and Google MCP Quirks](https://dev.to/gde/debugging-claude-code-and-google-mcp-quirks-8bd)

This one adds Google's newer cross-product server. The scripts, the sign-in handling and the skill layout carry over; the server, the scopes, the tests and the findings are new.

---

#### What is the Universal Search MCP Server?

Google hosts one MCP server per Workspace product: `gmailmcp`, `drivemcp`, `calendarmcp` and so on, each with its own tools. The Universal Search MCP server is a single extra server, `workspacemcp.googleapis.com`, with a single tool that fans one query out to Gmail, Drive, Calendar and Chat and returns the results together.

It is in Developer Preview, like the per-product servers. Google's guide documents Antigravity and Claude custom connectors; this setup adds Claude Code.

---

#### At This Point You Should Have…

- A Google Workspace account in the Developer Preview Program, with admin access to its Google Cloud project.
- The Google Cloud CLI (`gcloud`), signed in.
- Claude Code. This guide used version 2.1.294.
- Chrome on the same machine, for the consent screen and the OAuth sign-in page.
- A clone of the repository:

```bash
cd ~
git clone https://github.com/xbill9/workspace-search-mcp-claude
cd workspace-search-mcp-claude
```

---

#### The Server

`make probe` asks the server about itself without any credentials:

```bash
make probe
```

```plaintext
server              workspace-universal
url                 https://workspacemcp.googleapis.com/mcp/v1
advertises 2026-07-28  yes
versions            2024-11-05, 2025-03-26, 2025-06-18, 2025-11-25, 2026-07-28
legacy initialize   2025-11-25
tools               1: search_corpus
  search_corpus(pageSize, pageToken, query*)  readOnlyHint=True
resource scopes     9
  gmail     https://mail.google.com/, gmail.modify, gmail.readonly
  drive     drive, drive.readonly
  calendar  calendar, calendar.readonly
  chat      chat.messages, chat.messages.readonly
```

One tool, marked read-only, with one required argument. The server speaks the stateless 2026-07-28 MCP specification and every version from 2024-11-05 on, so any current client connects.

Each result item holds one of four shapes: a Gmail thread with its messages, a Drive file, a Calendar event, or a group of Chat messages. Each carries a `viewUrl`.

---

#### Step 1 — Enable the APIs

The server needs the Workspace MCP API plus the API of every product it searches:

```bash
./init.sh
```

`init.sh` runs this against the project in `~/project_id.txt`:

```bash
gcloud services enable gmail.googleapis.com \
    drive.googleapis.com \
    calendar-json.googleapis.com \
    chat.googleapis.com \
    workspacemcp.googleapis.com --project="$PROJECT_ID"
```

```plaintext
Operation "operations/acat.p2-…" finished successfully.
```

Google's guide for this server asks for no Chat app configuration, which the per-product Chat server needs.

---

#### Step 2 — Add the Scopes to the Consent Screen

One read-only scope turns on each product:

| Corpus | Scope (`https://www.googleapis.com/auth/…`) |
| :--- | :--- |
| Gmail | `gmail.readonly` |
| Drive | `drive.readonly` |
| Calendar | `calendar.readonly` |
| Chat | `chat.messages.readonly` |

Add them under **Google Auth Platform → Data Access → Add or remove scopes → Manually add scopes**, then **Update** and **Save**. A consent screen set up for the per-product servers already has `gmail.readonly`, `drive.readonly` and `chat.messages.readonly`; `calendar.readonly` is the one to add, because the Calendar server uses `calendar.events.readonly`.

After the reload the sensitive-scopes table went from 13 rows to 14.

---

#### Step 3 — Choose the OAuth Client

The server needs a Web application OAuth client with `http://localhost:8765/callback` as an authorized redirect URI. If you followed the companion article, you already have one.

Reusing it is one less console step. The cost is a shared grant: to Google, one OAuth client is one app, and signing any server on it in again while its token still works revokes every token that client issued. A separate client for search keeps its sign-ins apart from the eight per-product servers. This walk-through reused the existing client.

---

#### Step 4 — Register the Server

```bash
source ./save_oauth.sh
./claude_setup.sh
```

```plaintext
Adding workspace-universal to Claude Code (scope: user, corpora: gmail drive calendar chat)
Redirect URI required on the OAuth client: http://localhost:8765/callback

Added http MCP server workspace-universal to user config
Added HTTP MCP server workspace-developer with URL: https://workspace-developer.goog/mcp to user config
```

The script registers the server with `claude mcp add-json --client-secret`, so the client secret goes to Claude Code's credential store and never into a config file. The four scopes are pinned in `oauth.scopes`. `CORPORA="drive calendar" ./claude_setup.sh` pins a subset, and the server then searches only those products.

The name `workspace-universal` matches the one in Google's guide.

---

#### Step 5 — Sign In

Inside Claude Code, run `/mcp`, pick `workspace-universal`, then **Authenticate**. From your own terminal, `claude mcp login workspace-universal` does the same.

To have Claude drive the sign-in in Chrome, the skill uses a helper that prints the sign-in URL without needing a terminal:

```bash
./mcp_login.sh start
./mcp_login.sh check
```

```plaintext
Signed in: workspace-universal
```

The request Claude Code builds carries these parameters, with the four pinned scopes and no `access_type`:

```plaintext
host: accounts.google.com/o/oauth2/v2/auth
parameters: client_id, code_challenge, code_challenge_method, redirect_uri, resource, response_type, scope, state
resource: https://workspacemcp.googleapis.com/mcp/v1
access_type present: False
```

Google's consent page then lists four read-only permissions:

```plaintext
View your email messages and settings
See and download all your Google Drive files
See messages as well as their reactions and message content in Google Chat
See and download any calendar you can access using your Google Calendar
```

---

#### Step 6 — Check the Sign-In

```bash
make verify
```

```plaintext
server               registered  token    min left  refresh  corpora
workspace-universal  yes         valid          13  no       gmail,drive,calendar,chat

Google accepts the token; search_corpus can search 4 of 4 corpora.
No refresh token: this sign-in ends when the minutes reach zero.
```

`--verify` sends the token to Google's token-info endpoint, reads back the scopes Google granted, and maps them to products. A product missing from that list returns no results, whatever the query.

---

#### Step 7 — Search Without a Model

`mcp_search.sh` calls `search_corpus` directly with the token Claude Code stored and counts the results per product in code:

```bash
make search Q="meeting"
```

```plaintext
query: 'meeting'  arguments sent: {"query": "meeting"}

corpus    results
gmail           8
drive           9
calendar       13
chat            0
total          30

Gmail threads hold 8 messages; Chat results hold 0 messages.
```

A list of the results follows the table, one line each with its link. Other queries reached Chat too:

```plaintext
'standup'      gmail 10 drive 10 calendar  7 chat  2 total 29
'lunch'        gmail  9 drive  9 calendar 10 chat  2 total 30
'today'        gmail  8 drive  8 calendar 12 chat  2 total 30
'Q3 planning'  gmail 12 drive  9 calendar  8 chat  0 total 29
```

Matching is broad. The `Q3 planning` results include items about plans and planning in general, so a specific phrase does not narrow the search the way a quoted search in Gmail would.

---

#### Step 8 — Test Through Claude Code

```bash
make e2e
```

```plaintext
=== 2. Through Claude Code

server               result           calls  ok  err spilled
workspace-universal  PASS                 1   1    0       1

Claude Code saved the result to a file instead of passing it to the model (over its MCP output size limit); the model saw a preview. Counts below are from the server's result, which Claude Code records in the event stream.

Results per corpus, counted from the tool results: gmail 8, drive 10, calendar 12, chat 0
Queries the model sent: 'meeting'
```

The test runs a headless Claude Code session allowed only `search_corpus` and grades it from the session's tool calls and tool results. The `spilled` column is the next section.

---

#### What Does pageSize Do?

The schema offers `pageSize` and `pageToken`. Seven calls with the same query and different page sizes:

```plaintext
pageSize  gmail drive calendar chat total  chars nextPageToken
None          8     9       13    0    30  55076 False
1             9     9       12    0    30  56316 False
2             8     9       13    0    30  55076 False
3             8     9       13    0    30  55076 False
5             8    10       12    0    30  53002 False
10            8     9       13    0    30  55076 False
50            8     9       13    0    30  55076 False
```

Every call returned 30 items and no `nextPageToken`, so `pageSize` has no effect and there is no second page. The tool's own description says "Pagination is not supported for cross-corpus search."

The split across products also moves between identical calls:

```plaintext
run 1        8     9       13    0    30  55076 False
run 2        8    10       12    0    30  53002 False
run 3        8    10       12    0    30  53002 False
```

So a per-product count describes one response. Comparing it with the count from another call measures the server's ranking, which shifts.

---

#### Known Issue: Results Are Too Large for Claude Code

Thirty items is a lot of text. Calendar results carry whole meeting invitations, dial-in numbers included, and Chat results carry their conversations. Responses in these runs measured from 53,002 to 111,795 characters.

Claude Code 2.1.294 caps what an MCP tool passes to the model. Over the cap, it saves the result to a file and hands the model a notice:

```plaintext
Error: result (52,547 characters) exceeds maximum allowed tokens. Output has been saved to <path>
Format: JSON with schema: {items: [{...}]}
Use jq to make structured queries (find a value, filter by field).
```

The tool result carries no error flag, so the call looks successful. Raising `MAX_MCP_OUTPUT_TOKENS` to 50000 moves the result past the first cap and into a second, size-based one:

```plaintext
<persisted-output>
Output too large (51.3KB). Full output saved to: <path>
```

The model then sees a 2 KB preview. Claude Code still records the server's full result in its event stream (`tool_use_result.structuredContent`, 30 items), which is where `mcp_test.sh` counts from.

In practice, Claude reads the saved file with `jq` when it has a shell, and `mcp_search.sh` gives exact counts with no model in the loop.

---

#### Known Issue: Sign-Ins Last About an Hour

The sign-in request in Step 5 has no `access_type=offline`, and Google issues refresh tokens only through that parameter. Claude Code asks for a refresh token the MCP way, with the `offline_access` scope, and only when the authorization server lists it; Google's OpenID configuration lists `openid`, `email` and `profile`.

So `--verify` shows `refresh no`, and the sign-in ends after an hour. The debugging article covers the investigation and two ways past the hour, a `headersHelper` and a local proxy. Both helpers in the companion repository now know `workspace-universal`.

---

#### Known Issue: One OAuth Client, One Grant

Google revokes the whole grant for an OAuth client when one of its tokens is revoked, and Claude Code revokes the old token whenever a server is signed in again. With one search server that is easy to plan around: sign in again only when `--verify` says `expired` or `revoked`.

The grant reaches further when the client is shared. With the client from the companion article, signing `workspace-universal` in again while its token works also signs out Gmail, Drive and the other per-product servers, and the reverse.

---

#### Using the Skill — Install It

The repository is a Claude Code plugin marketplace:

```plaintext
/plugin marketplace add xbill9/workspace-search-mcp-claude
/plugin install google-workspace-search-mcp@workspace-search-mcp-claude
```

Then ask Claude Code something like *"set up Workspace search"*. The skill checks what is already done, runs only the missing steps, walks through the console steps or drives them in Chrome when asked, signs in, and tests.

---

#### Using the Skill — What to Ask

Once signed in, restart Claude Code so the tool loads, then ask questions that span products:

*"Find anything related to Project X across my email, docs, and chat messages."*

*"When is my next meeting about the marketing plan, and what are the latest notes and chat messages on it?"*

For "how many" questions the skill runs `mcp_search.sh --json` and quotes its counts.

---

#### Using the Skill — What Is Inside

- `SKILL.md`: the workflow, the troubleshooting table, and how to search.
- `scripts/`: `bootstrap.sh`, `claude_setup.sh`, `mcp_login.sh`, `mcp_status.sh`, `mcp_search.sh`, `mcp_test.sh`, `mcp_probe.sh`, and `wsearch.py`, which does every count, comparison and grade.
- `references/`: the tool schema and scopes, the console steps, the known issues, the quirks, and other MCP clients.

---

#### Testing the Setup

```bash
make test
```

```plaintext
--- syntax: ok
--- shellcheck: ok
--- unit (wsearch.py): ok
--- consistency: ok
--- scripts (stub claude): ok
--- plugin validate: ok
0 stage(s) failed.
```

The offline suite needs no sign-in and no network. The unit tests cover the scope-to-product mapping, token selection, response parsing, per-product counting, and grading of passing, failing, never-called and spilled sessions. The consistency tests fail if the server name, URL, scopes or APIs drift between the scripts, the configs, the docs and the manifests, or if `offline_access` reaches the pinned scopes. The script tests run `claude_setup.sh` against a stand-in `claude` and check that the client secret arrives only through the environment, never in arguments or output.

`make test-live` adds the server check, the sign-in check and the end-to-end test.

---

#### 🔎 Tip: Count in Code, Quote the Count

A search returns 30 items across four shapes, with threads that hold several messages. Asking a model to count them is the job a script does exactly. `wsearch.py` counts per product and counts the messages inside threads separately; the skill quotes those numbers.

Check the query too: an exact count for the wrong query is still the wrong answer, and `mcp_search.sh` prints the arguments it sent above the table.

---

#### 🔎 Tip: A Missing Product Is Usually a Missing Scope

Google's guide says the server searches only the products whose scope the sign-in granted, so unticking a permission on the consent page leaves that product out. `make verify` lists the products the granted scopes cover, so a product that never returns anything is a one-command check.

---

#### 🔎 Tip: ✔ Connected Means the Server Answered

The server lists its tool without a token, so `claude mcp list` shows `✔ Connected` before any sign-in and after a token is revoked. A tool call without a token returns "Method doesn't allow unregistered callers". Use `make verify` for sign-in state.

---

#### Compare and Contrast

| | Per-product servers | Universal Search |
| :--- | :--- | :--- |
| Servers to register | 8 | 1 |
| Tools | 59, read and write | 1, read-only |
| Scopes | 21 across the eight | 4, one per product |
| Sign-ins | 8, together | 1 |
| Result size control | per tool | none: about 30 items |
| Console extras | Chat app configuration | none |
| Best for | acting on one product | finding something when you do not know where it is |

Both can be registered side by side. The search tool's description tells the model to call it first when a question names no product, and to fall back to per-product tools only when it finds nothing.

---

#### So, Which One?

For finding things, Universal Search: one server, one sign-in, four read-only scopes, and one call across every product. Use `mcp_search.sh` when you need numbers.

For acting on what you find, such as reading a whole document, drafting a reply or checking free time, keep the per-product servers. Give search its own OAuth client if you run both, so one sign-in never undoes the other.

---

#### Summary

The goal of this article was to connect Claude Code to Google's Universal Search MCP server and package the setup as a Claude Code skill with tests. The key to the solution was scripting every step that has an API and computing every count and grade in code, from the server's own result. The results were:

- 🟢 **One read-only tool searches Gmail, Drive, Calendar and Chat**, and all four returned results through a live sign-in.
- 🟢 **The live test passes** directly and through a headless Claude Code session, graded from the tool results.
- 🟢 **The offline suite passes** all six stages with no sign-in and no network.
- 🟢 **Four read-only scopes**, pinned, one per product, and `make verify` maps the granted ones back to products.
- ⚠️ **`pageSize` has no effect**: every search returned about 30 items, and the per-product split shifts between identical calls.
- ❌ **Results exceed Claude Code's MCP output limit**, so the model gets a saved file and a preview.
- ⚠️ **Sign-ins last about an hour**, with no refresh token issued.

Scope: one Google Workspace account in the Developer Preview, one Google Cloud project with an Internal consent screen, one Web application OAuth client shared with the eight per-product servers, Claude Code 2.1.294 on Linux, measured on 2026-10-08. Counts come from one mailbox and change with its contents and with the server's ranking. A separate OAuth client for search and the claude.ai connector were not tested.

The strategy for using MCP with Google Workspace Universal Search from Claude Code was validated with an incremental step by step approach.

---

#### References

* [workspace-search-mcp-claude | GitHub](https://github.com/xbill9/workspace-search-mcp-claude)
* [Universal Search MCP Server for Workspace | Google for Developers](https://developers.google.com/workspace/guides/universal-search-mcp)
* [Configure the Google Workspace MCP servers | Google for Developers](https://developers.google.com/workspace/guides/configure-mcp-servers)
* [Google Workspace Developer Preview Program | Google for Developers](https://developers.google.com/workspace/preview)
* [Connect Claude Code to tools via MCP | Claude Code Docs](https://code.claude.com/docs/en/mcp)
* [MCP Configuration for Google Workspace with Claude Code | dev.to](https://dev.to/gde/mcp-configuration-for-google-workspace-with-claude-code-11om)
* [Debugging Claude Code and Google MCP Quirks | dev.to](https://dev.to/gde/debugging-claude-code-and-google-mcp-quirks-8bd)
