#!/bin/bash

# Run the test suite.
#
#   tests/run.sh          offline: syntax, shellcheck, unit, consistency, script behaviour
#   tests/run.sh --live   also the no-credential probe and, when signed in,
#                         mcp_status.sh --verify and mcp_test.sh
#
# Exit status is the number of failed stages.

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
SCRIPTS="$ROOT/plugin/skills/google-workspace-search-mcp/scripts"
FAILED=0
export PYTHONDONTWRITEBYTECODE=1

stage() {  # stage <name> <command...>
    local name=$1
    shift
    echo "=== $name"
    if "$@"; then
        echo "--- $name: ok"
    else
        echo "--- $name: FAIL"
        FAILED=$((FAILED + 1))
    fi
    echo ""
}

# shellcheck disable=SC2329  # called through stage
syntax() {
    local f rc=0
    for f in "$ROOT"/*.sh "$SCRIPTS"/*.sh "$ROOT"/tests/*.sh; do
        bash -n "$f" || rc=1
    done
    python3 -c "import ast, sys; ast.parse(open(sys.argv[1]).read())" "$SCRIPTS/wsearch.py" || rc=1
    return "$rc"
}

# shellcheck disable=SC2329  # called through stage
lint() {
    if ! command -v shellcheck > /dev/null; then
        echo "shellcheck not installed; skipped"
        return 0
    fi
    shellcheck "$ROOT"/*.sh "$SCRIPTS"/*.sh "$ROOT"/tests/*.sh
}

stage "syntax" syntax
stage "shellcheck" lint
stage "unit (wsearch.py)" python3 -m unittest discover -s "$ROOT/tests" -p 'test_wsearch.py'
stage "consistency" python3 -m unittest discover -s "$ROOT/tests" -p 'test_consistency.py'
stage "scripts (stub claude)" "$ROOT/tests/test_scripts.sh"
if command -v claude > /dev/null; then
    stage "plugin validate" bash -c "claude plugin validate '$ROOT' && claude plugin validate '$ROOT/plugin'"
fi

if [ "$1" = "--live" ]; then
    stage "live probe (no credentials)" "$SCRIPTS/mcp_probe.sh"
    if "$SCRIPTS/mcp_status.sh" --verify; then
        stage "live end-to-end" "$SCRIPTS/mcp_test.sh"
    else
        echo "Not signed in: skipped the live end-to-end test."
        echo "Sign in with /mcp or 'claude mcp login workspace-universal', then re-run."
    fi
fi

echo "$FAILED stage(s) failed."
exit "$FAILED"
