#!/bin/bash

# Read-only end-to-end test of workspace-universal.
#
#   mcp_test.sh [--direct] [query]
#
# 1. Direct: calls search_corpus with the stored token (mcp_search.sh) and
#    reports the result count per corpus. No model involved.
# 2. Through Claude Code: one headless session (`claude -p`) allowed only
#    search_corpus, asked to run the query. Pass or fail is computed from the
#    session's stream-json tool calls and results, and so are the per-corpus
#    counts, not from the model's summary.
#
# --direct runs step 1 only. The query defaults to $MCP_TEST_QUERY or
# "meeting". With MCP_SCOPE=local registrations, run it from the directory the
# server was registered for. Exit status is 0 only if every step passes.

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
TIMEOUT=${MCP_TEST_TIMEOUT:-300}
DIRECT_ONLY=0
if [ "$1" = "--direct" ]; then
    DIRECT_ONLY=1
    shift
fi
QUERY="${*:-${MCP_TEST_QUERY:-meeting}}"
RC=0

echo "=== 1. Direct search_corpus call"
# Counts only: the per-result lines (other people's content) are cut.
python3 "$SCRIPT_DIR/wsearch.py" search "$QUERY" --page-size 10 | sed '/^Results/,$d'
if [ "${PIPESTATUS[0]}" -eq 0 ]; then
    echo "direct: PASS"
else
    echo "direct: FAIL"
    RC=1
fi

[ "$DIRECT_ONLY" = 1 ] && exit $RC

echo ""
echo "=== 2. Through Claude Code"
PROMPT="Test the Universal Search MCP server. Read only. Call the workspace-universal
search_corpus tool exactly once with query \"$QUERY\" and pageSize 10.
Reply with one line: done."

EVENTS=$(mktemp)
trap 'rm -f "$EVENTS"' EXIT
timeout "$TIMEOUT" claude -p "$PROMPT" \
    --allowedTools "mcp__workspace-universal__search_corpus" \
    --output-format stream-json --verbose > "$EVENTS" 2>/dev/null
python3 "$SCRIPT_DIR/wsearch.py" grade "$EVENTS" || RC=1

exit $RC
