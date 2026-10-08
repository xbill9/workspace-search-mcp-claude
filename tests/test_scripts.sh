#!/bin/bash

# Script behaviour with a stub `claude` on PATH: no network, no real
# registration, no credentials. Each check prints ok or FAIL; exit status is
# the number of failures.

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
SCRIPTS="$ROOT/plugin/skills/google-workspace-search-mcp/scripts"
WORK=$(mktemp -d)
trap 'rm -rf "$WORK"' EXIT
FAILS=0

check() {  # check <description> <command...>
    local desc=$1
    shift
    if "$@" > /dev/null 2>&1; then
        echo "ok    $desc"
    else
        echo "FAIL  $desc"
        FAILS=$((FAILS + 1))
    fi
}

# Stub: records argv and whether MCP_CLIENT_SECRET was in its environment.
mkdir -p "$WORK/bin"
cat > "$WORK/bin/claude" <<'EOF'
#!/bin/bash
{
    printf 'ARGS'
    printf ' %q' "$@"
    printf '\n'
    [ -n "$MCP_CLIENT_SECRET" ] && echo "SECRET_IN_ENV $MCP_CLIENT_SECRET"
} >> "$STUB_LOG"
EOF
chmod +x "$WORK/bin/claude"
export PATH="$WORK/bin:$PATH" STUB_LOG="$WORK/claude.log"

run_setup() {  # run_setup [VAR=value ...]
    : > "$STUB_LOG"
    env CLIENT_ID=test-client.apps.googleusercontent.com CLIENT_SECRET=s3cret-value "$@" \
        "$SCRIPTS/claude_setup.sh"
}

# --- claude_setup.sh -------------------------------------------------------
run_setup > "$WORK/out" 2>&1
check "claude_setup.sh exits 0" test $? -eq 0
check "registers workspace-universal with add-json --client-secret" \
    grep -q "^ARGS mcp add-json --client-secret -s user workspace-universal" "$STUB_LOG"
check "uses the workspacemcp URL" grep -q 'workspacemcp.googleapis.com/mcp/v1' "$STUB_LOG"
for s in gmail.readonly drive.readonly calendar.readonly chat.messages.readonly; do
    check "pins scope $s" grep -q "auth/$s" "$STUB_LOG"
done
check "secret passed through the environment" grep -q "^SECRET_IN_ENV s3cret-value" "$STUB_LOG"
check "secret never in argv" bash -c "! grep '^ARGS' '$STUB_LOG' | grep -q s3cret-value"
check "secret never printed" bash -c "! grep -q s3cret-value '$WORK/out'"
check "callback port 8765 by default" grep -q 'callbackPort\\":8765' "$STUB_LOG"
check "registers workspace-developer" grep -q "^ARGS mcp add --transport http -s user workspace-developer" "$STUB_LOG"
check "no offline_access scope" bash -c "! grep -q offline_access '$STUB_LOG'"

# The add-json payload is valid JSON with the expected shape.
JSON_OK=$(python3 - "$STUB_LOG" <<'EOF'
import json, shlex, sys
for line in open(sys.argv[1]):
    if line.startswith("ARGS mcp add-json"):
        cfg = json.loads(shlex.split(line)[-1])
        ok = (cfg["type"] == "http" and cfg["oauth"]["clientId"].startswith("test-client")
              and len(cfg["oauth"]["scopes"].split()) == 4 and "clientSecret" not in cfg["oauth"])
        print("yes" if ok else "no")
EOF
)
check "add-json payload is valid JSON without the secret" test "$JSON_OK" = yes

run_setup CORPORA="drive chat" > /dev/null 2>&1
check "CORPORA=drive chat pins exactly two scopes" python3 - "$STUB_LOG" <<'EOF'
import json, shlex, sys
for line in open(sys.argv[1]):
    if line.startswith("ARGS mcp add-json"):
        scopes = json.loads(shlex.split(line)[-1])["oauth"]["scopes"].split()
        sys.exit(0 if [s.rsplit("/", 1)[1] for s in scopes] == ["drive.readonly", "chat.messages.readonly"] else 1)
sys.exit(1)
EOF

run_setup CORPORA="gmail photos" > /dev/null 2>&1
check "unknown corpus is rejected" test $? -ne 0

run_setup MCP_SCOPE=local CALLBACK_PORT=9999 > /dev/null 2>&1
check "MCP_SCOPE and CALLBACK_PORT are honoured" \
    bash -c "grep -q -- '-s local workspace-universal' '$STUB_LOG' && grep -q 'callbackPort\\\\\":9999' '$STUB_LOG'"

: > "$STUB_LOG"
HOME="$WORK/emptyhome" CLIENT_ID="" CLIENT_SECRET="" "$SCRIPTS/claude_setup.sh" > /dev/null 2>&1
check "missing OAuth client exits non-zero" test $? -ne 0
check "missing OAuth client registers nothing" test ! -s "$STUB_LOG"

# --- mcp_login.sh ------------------------------------------------------------
"$SCRIPTS/mcp_login.sh" start gmail > /dev/null 2>&1
check "mcp_login.sh refuses other server names" test $? -eq 2
TMPDIR="$WORK" "$SCRIPTS/mcp_login.sh" check > /dev/null 2>&1
check "mcp_login.sh check defaults to workspace-universal and reports not signed in" test $? -eq 1

# --- mcp_search.sh / wsearch.py ----------------------------------------------
"$SCRIPTS/mcp_search.sh" > /dev/null 2>&1
check "mcp_search.sh without a query prints usage" test $? -eq 2
HOME="$WORK/emptyhome" python3 "$SCRIPTS/wsearch.py" search test > /dev/null 2>&1
check "search without a stored token exits 2, no network call" test $? -eq 2
python3 "$SCRIPTS/wsearch.py" grade "$ROOT/tests/fixtures/stream-pass.jsonl" > /dev/null
check "grade passes the PASS fixture" test $? -eq 0
python3 "$SCRIPTS/wsearch.py" grade "$ROOT/tests/fixtures/stream-fail.jsonl" > /dev/null
check "grade fails the FAIL fixture" test $? -eq 1

echo ""
echo "$FAILS failure(s)."
exit "$FAILS"
