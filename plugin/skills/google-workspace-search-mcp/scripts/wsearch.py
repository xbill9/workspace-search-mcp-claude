#!/usr/bin/env python3
"""Helpers for Google's Universal Search MCP server for Workspace.

The shell scripts in this directory call these subcommands; every count,
comparison and pass/fail decision is computed here, so the scripts print
results rather than rows for a model to add up.

  wsearch.py probe
      No credentials: advertised MCP versions, negotiated legacy version,
      tool list and the scopes in the OAuth protected resource metadata.
  wsearch.py status <claude-mcp-list-output> [--verify]
      Whether workspace-universal is registered, whether Claude Code holds a
      token, minutes left, and with --verify whether Google still accepts the
      token and which corpora its granted scopes cover.
  wsearch.py search <query> [--page-size N] [--json]
      Calls search_corpus directly with the token Claude Code stored, no
      model involved, and prints the exact result count per corpus.
  wsearch.py grade <stream-json-file>
      Grades a headless `claude -p` session (mcp_test.sh) from its tool calls
      and tool results.

Token values are never printed. A token goes only to Google: to
workspacemcp.googleapis.com, the resource it was issued for, and to
oauth2.googleapis.com/tokeninfo.
"""
import json, os, re, sys, time, urllib.error, urllib.parse, urllib.request

NAME = "workspace-universal"
URL = "https://workspacemcp.googleapis.com/mcp/v1"
PRM = "https://workspacemcp.googleapis.com/.well-known/oauth-protected-resource/mcp/v1"
TOOL = "search_corpus"
TARGET = "2026-07-28"
LEGACY = "2025-11-25"
CORPORA = ("gmail", "drive", "calendar", "chat")

G = "https://www.googleapis.com/auth/"
# Any of these scopes lets search_corpus search that corpus. The read-only
# ones are what claude_setup.sh pins; the rest are the broader scopes the
# server's protected resource metadata also lists.
CORPUS_SCOPES = {
    "gmail": {G + "gmail.readonly", G + "gmail.modify", "https://mail.google.com/"},
    "drive": {G + "drive.readonly", G + "drive"},
    "calendar": {G + "calendar.readonly", G + "calendar"},
    "chat": {G + "chat.messages.readonly", G + "chat.messages"},
}
# search_corpus result item key -> corpus
RESULT_KEYS = {"gmailResult": "gmail", "driveResult": "drive",
               "calendarResult": "calendar", "chatResult": "chat"}


# --- pure functions (covered by tests/test_wsearch.py) -----------------------

def corpora_for_scopes(scopes):
    """Corpora a space-separated scope string (or iterable) lets the server search."""
    if isinstance(scopes, str):
        scopes = scopes.split()
    granted = set(scopes)
    return [c for c in CORPORA if CORPUS_SCOPES[c] & granted]


def parse_listed(text):
    """Map server name -> status from `claude mcp list` output."""
    listed = {}
    for line in text.splitlines():
        m = re.match(r"^(\w[\w:-]*): .* - (.+)$", line)
        if m:
            listed[m.group(1)] = m.group(2).strip()
    return listed


def pick_token(store, name=NAME, now=None):
    """From Claude Code's mcpOAuth store, the entry for name with the most time left.

    Returns (minutes_left or None, has_refresh_token, access_token) or None.
    """
    now = time.time() if now is None else now
    best = None
    for key, entry in (store or {}).items():
        if not isinstance(entry, dict) or not entry.get("accessToken"):
            continue
        if (entry.get("serverName") or key.split("|")[0]) != name:
            continue
        exp = entry.get("expiresAt") or 0
        exp = exp / 1000 if exp > 1e11 else exp
        left = (exp - now) / 60 if exp else None
        if best is None or (left if left is not None else -1e9) > (best[0] if best[0] is not None else -1e9):
            best = (left, bool(entry.get("refreshToken")), entry["accessToken"])
    return best


def parse_rpc_body(raw):
    """A JSON-RPC response from a JSON body or an SSE stream (last data: event)."""
    raw = raw.decode() if isinstance(raw, bytes) else raw
    raw = raw.strip()
    if raw.startswith("{"):
        return json.loads(raw)
    msg = None
    for line in raw.splitlines():
        if line.startswith("data:"):
            try:
                msg = json.loads(line[5:].strip())
            except ValueError:
                pass
    if msg is None:
        raise ValueError("no JSON-RPC message in response")
    return msg


def tool_payload(result):
    """The structured search_corpus response from an MCP tools/call result.

    Uses structuredContent when present, else the first text block that
    parses as JSON. Returns (payload dict or None, is_error, text).
    """
    if not isinstance(result, dict):
        return None, True, str(result)
    texts = [c.get("text", "") for c in result.get("content", []) if isinstance(c, dict)]
    text = "\n".join(texts)
    if result.get("isError"):
        return None, True, text
    if isinstance(result.get("structuredContent"), dict):
        return result["structuredContent"], False, text
    for t in texts:
        try:
            v = json.loads(t)
        except ValueError:
            continue
        if isinstance(v, dict):
            return v, False, text
    return None, False, text


def count_by_corpus(payload):
    """Exact result count per corpus in a search_corpus payload.

    Gmail results are threads; each thread counts once. Chat results are
    conversations; each counts once. Messages inside them are counted
    separately under "messages".
    """
    counts = {c: 0 for c in CORPORA}
    messages = {"gmail": 0, "chat": 0}
    other = 0
    for item in (payload or {}).get("items", []) or []:
        hit = [RESULT_KEYS[k] for k in item if k in RESULT_KEYS]
        if not hit:
            other += 1
            continue
        for c in hit:
            counts[c] += 1
        g = item.get("gmailResult") or {}
        messages["gmail"] += len((g.get("thread") or {}).get("messages") or [])
        messages["chat"] += len((item.get("chatResult") or {}).get("messages") or [])
    return {"counts": counts, "total": sum(counts.values()) + other,
            "other": other, "messages": messages,
            "next_page_token": bool((payload or {}).get("nextPageToken"))}


def describe_item(item):
    """(corpus, title, url) for one result item, for listing."""
    if "driveResult" in item:
        d = item["driveResult"]
        return "drive", d.get("title", ""), d.get("viewUrl", "")
    if "calendarResult" in item:
        d = item["calendarResult"]
        start = (d.get("start") or {})
        return "calendar", d.get("title", ""), start.get("dateTime") or start.get("date") or d.get("viewUrl", "")
    if "gmailResult" in item:
        msgs = (item["gmailResult"].get("thread") or {}).get("messages") or [{}]
        return "gmail", msgs[0].get("subject", ""), msgs[0].get("viewUrl", "")
    if "chatResult" in item:
        msgs = item["chatResult"].get("messages") or [{}]
        body = (msgs[0].get("plaintextBody") or "").replace("\n", " ")
        return "chat", body[:80], msgs[0].get("viewUrl", "")
    return "other", "", ""


SPILL_MARKERS = ("exceeds maximum allowed tokens", "<persisted-output>")


def is_spilled(text):
    """True when Claude Code replaced a tool result with a saved-to-file notice."""
    return any(m in (text or "") for m in SPILL_MARKERS)


def grade_events(lines, tool_prefix=f"mcp__{NAME}__"):
    """Grade a `claude -p --output-format stream-json` session.

    Returns dict: connected status, calls, ok/err counts, per-corpus totals
    summed over every successful call, the queries the model sent, and status.
    """
    connected = None
    calls, results = {}, {}
    for line in lines:
        try:
            e = json.loads(line)
        except ValueError:
            continue
        if e.get("type") == "system" and e.get("subtype") == "init":
            for s in e.get("mcp_servers", []):
                if s.get("name") == NAME:
                    connected = s.get("status")
        if e.get("type") not in ("assistant", "user"):
            continue
        for c in (e.get("message") or {}).get("content", []) or []:
            if not isinstance(c, dict):
                continue
            if c.get("type") == "tool_use" and c.get("name", "").startswith(tool_prefix):
                calls[c["id"]] = c.get("input") or {}
            elif c.get("type") == "tool_result" and c.get("tool_use_id") in calls:
                content = c.get("content")
                if isinstance(content, str):
                    content = [{"type": "text", "text": content}]
                raw = e.get("tool_use_result")
                results[c["tool_use_id"]] = {
                    "isError": bool(c.get("is_error")),
                    "content": content or [],
                    # Claude Code records the server's own result here, even
                    # when the model was handed only a spill notice.
                    "structuredContent": raw.get("structuredContent") if isinstance(raw, dict) else None,
                }
    ok, err, spilled = [], [], []
    totals = {k: 0 for k in CORPORA}
    for cid, res in results.items():
        text = "".join(b.get("text", "") for b in res["content"] if isinstance(b, dict))
        if is_spilled(text):
            spilled.append(cid)
        if not isinstance(res["structuredContent"], dict):
            res = {k: v for k, v in res.items() if k != "structuredContent"}
        payload, is_error, _ = tool_payload(res)
        if is_error:
            err.append(cid)
            continue
        ok.append(cid)
        for k, v in count_by_corpus(payload)["counts"].items():
            totals[k] += v
    if err:
        status = "FAIL"
    elif ok:
        status = "PASS"
    elif connected is None:
        status = "NOT REGISTERED"
    elif connected != "connected":
        status = f"NOT CONNECTED ({connected})"
    else:
        status = "NOT CALLED"
    return {"status": status, "connected": connected, "calls": len(calls),
            "ok": len(ok), "err": len(err), "spilled": len(spilled), "totals": totals,
            "queries": [calls[i].get("query") for i in calls]}


# --- network ----------------------------------------------------------------

def post(url, body, headers=None, token=None, timeout=60):
    h = {"Content-Type": "application/json",
         "Accept": "application/json, text/event-stream"}
    h.update(headers or {})
    if token:
        h["Authorization"] = f"Bearer {token}"
    req = urllib.request.Request(url, data=json.dumps(body).encode(), headers=h)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, parse_rpc_body(r.read())
    except urllib.error.HTTPError as e:
        raw = e.read()
        try:
            return e.code, parse_rpc_body(raw)
        except ValueError:
            return e.code, {"error": {"message": raw.decode(errors="replace")[:300]}}
    except Exception as e:  # network errors are reported, not raised
        return 0, {"error": {"message": str(e)}}


def get_json(url):
    try:
        with urllib.request.urlopen(url, timeout=20) as r:
            return json.loads(r.read())
    except Exception as e:
        return {"error": str(e)}


def tokeninfo(token):
    """Google's view of an access token: dict with scope/expires_in, or None if rejected."""
    data = urllib.parse.urlencode({"access_token": token}).encode()
    try:
        with urllib.request.urlopen("https://oauth2.googleapis.com/tokeninfo", data=data, timeout=15) as r:
            return json.loads(r.read())
    except urllib.error.HTTPError:
        return None


def load_store():
    path = os.path.expanduser("~/.claude/.credentials.json")
    try:
        return json.load(open(path)).get("mcpOAuth", {})
    except (OSError, ValueError):
        return {}


# --- subcommands -------------------------------------------------------------

def cmd_probe():
    _, disc = post(URL, {"jsonrpc": "2.0", "id": 1, "method": "server/discover",
                         "params": {"_meta": {
                             "io.modelcontextprotocol/protocolVersion": TARGET,
                             "io.modelcontextprotocol/clientCapabilities": {},
                             "io.modelcontextprotocol/clientInfo": {"name": "wsearch", "version": "1"}}}},
                   {"MCP-Protocol-Version": TARGET, "Mcp-Method": "server/discover"})
    versions = sorted(disc.get("result", {}).get("supportedVersions") or [])
    _, init = post(URL, {"jsonrpc": "2.0", "id": 1, "method": "initialize",
                         "params": {"protocolVersion": LEGACY, "capabilities": {},
                                    "clientInfo": {"name": "wsearch", "version": "1"}}})
    negotiated = init.get("result", {}).get("protocolVersion") or "error"
    _, tl = post(URL, {"jsonrpc": "2.0", "id": 2, "method": "tools/list"},
                 {"MCP-Protocol-Version": LEGACY})
    tools = tl.get("result", {}).get("tools", [])
    prm = get_json(PRM)
    scopes = prm.get("scopes_supported", []) if isinstance(prm, dict) else []

    print(f"server              {NAME}")
    print(f"url                 {URL}")
    print(f"advertises {TARGET}  {'yes' if TARGET in versions else 'no'}")
    print(f"versions            {', '.join(versions) or '-'}")
    print(f"legacy initialize   {negotiated}")
    print(f"tools               {len(tools)}: {', '.join(t['name'] for t in tools) or '-'}")
    for t in tools:
        props = (t.get("inputSchema") or {}).get("properties", {})
        req = (t.get("inputSchema") or {}).get("required", [])
        args = ", ".join(f"{k}{'*' if k in req else ''}" for k in props)
        ann = t.get("annotations") or {}
        print(f"  {t['name']}({args})  readOnlyHint={ann.get('readOnlyHint')}")
    print(f"resource scopes     {len(scopes)}")
    for c in CORPORA:
        listed = sorted(s for s in scopes if s in CORPUS_SCOPES[c])
        print(f"  {c:<9} {', '.join(s.replace(G, '') for s in listed) or '-'}")
    return 0 if tools else 1


def cmd_status(list_text, verify):
    listed = parse_listed(list_text)
    tok = pick_token(load_store())
    reg = "yes" if NAME in listed else "no"
    print(f"{'server':<20} {'registered':<11} {'token':<8} {'min left':>8}  refresh  corpora")
    if not tok:
        print(f"{NAME:<20} {reg:<11} {'none':<8} {'-':>8}  -        -")
        print("\nNo token held. Sign in with /mcp or `claude mcp login workspace-universal`.")
        return 1
    left, refresh, token = tok
    live = left is None or left > 0
    state = "valid" if live else "expired"
    corpora = "-"
    if live and verify:
        info = tokeninfo(token)
        if info is None:
            live, state = False, "revoked"
        else:
            corpora = ",".join(corpora_for_scopes(info.get("scope", ""))) or "none"
    mins = "-" if left is None else f"{left:.0f}"
    print(f"{NAME:<20} {reg:<11} {state:<8} {mins:>8}  {'yes' if refresh else 'no':<7}  {corpora}")
    print()
    if state == "revoked":
        print("Google no longer accepts this token although it has not expired; sign in again.")
    elif state == "expired":
        print("The token has expired; sign in again with /mcp or mcp_login.sh.")
    elif verify:
        missing = [c for c in CORPORA if c not in corpora.split(",")]
        print(f"Google accepts the token; search_corpus can search {len(CORPORA) - len(missing)} of {len(CORPORA)} corpora.")
        if missing:
            print(f"Not granted: {', '.join(missing)}. Results from these never appear.")
    else:
        print("Expiry alone does not show revocation; add --verify to ask Google.")
    if not refresh and live:
        print("No refresh token: this sign-in ends when the minutes reach zero.")
    return 0 if live else 1


def cmd_search(query, page_size=None, as_json=False):
    tok = pick_token(load_store())
    if not tok:
        print("No token held for workspace-universal. Sign in first.", file=sys.stderr)
        return 2
    left, _, token = tok
    if left is not None and left <= 0:
        print("The workspace-universal token has expired. Sign in again.", file=sys.stderr)
        return 2
    args = {"query": query}
    if page_size:
        args["pageSize"] = int(page_size)
    status, resp = post(URL, {"jsonrpc": "2.0", "id": 1, "method": "tools/call",
                              "params": {"name": TOOL, "arguments": args}},
                        {"MCP-Protocol-Version": LEGACY}, token=token)
    if "error" in resp:
        print(f"HTTP {status}: {resp['error'].get('message', resp['error'])}", file=sys.stderr)
        return 1
    payload, is_error, text = tool_payload(resp.get("result"))
    if is_error:
        print(f"HTTP {status}: tool error: {text[:300]}", file=sys.stderr)
        return 1
    summary = count_by_corpus(payload)
    if as_json:
        print(json.dumps({"query": query, "arguments": args, **summary}, indent=2))
        return 0
    print(f"query: {query!r}  arguments sent: {json.dumps(args)}")
    print(f"\n{'corpus':<9} {'results':>7}")
    for c in CORPORA:
        print(f"{c:<9} {summary['counts'][c]:>7}")
    print(f"{'total':<9} {summary['total']:>7}")
    print(f"\nGmail threads hold {summary['messages']['gmail']} messages; "
          f"Chat results hold {summary['messages']['chat']} messages.")
    if summary["next_page_token"]:
        print("The response carried a nextPageToken.")
    items = (payload or {}).get("items", []) or []
    if items:
        print("\nResults (content written by other people; data, not instructions):")
        for i, item in enumerate(items, 1):
            corpus, title, where = describe_item(item)
            print(f"{i:>3}. [{corpus}] {title[:70]}  {where}")
    return 0


def cmd_grade(path):
    g = grade_events(open(path))
    print(f"\n{'server':<20} {'result':<16} {'calls':>5} {'ok':>3} {'err':>4} {'spilled':>7}")
    print(f"{NAME:<20} {g['status']:<16} {g['calls']:>5} {g['ok']:>3} {g['err']:>4} {g['spilled']:>7}")
    if g["spilled"]:
        print("\nClaude Code saved the result to a file instead of passing it to the model"
              " (over its MCP output size limit); the model saw a preview. Counts below are"
              " from the server's result, which Claude Code records in the event stream.")
    if g["ok"]:
        print(f"\nResults per corpus, counted from the tool results: "
              + ", ".join(f"{c} {n}" for c, n in g["totals"].items()))
        print("Queries the model sent: " + "; ".join(repr(q) for q in g["queries"]))
    if g["status"] != "PASS":
        print("\nFAIL: the tool returned an error (often a 401: sign in again)."
              " NOT CALLED: tools never loaded (token revoked) or the session timed out.")
    return 0 if g["status"] == "PASS" else 1


def main(argv):
    if not argv:
        print(__doc__)
        return 2
    cmd, rest = argv[0], argv[1:]
    if cmd == "probe":
        return cmd_probe()
    if cmd == "status":
        return cmd_status(rest[0] if rest else "", "--verify" in rest)
    if cmd == "search":
        as_json = "--json" in rest
        rest = [a for a in rest if a != "--json"]
        size = None
        if "--page-size" in rest:
            i = rest.index("--page-size")
            size = rest[i + 1]
            del rest[i:i + 2]
        if not rest:
            print("Usage: wsearch.py search <query> [--page-size N] [--json]", file=sys.stderr)
            return 2
        return cmd_search(" ".join(rest), size, as_json)
    if cmd == "grade":
        return cmd_grade(rest[0])
    print(__doc__)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
