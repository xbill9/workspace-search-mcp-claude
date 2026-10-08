#!/bin/bash

# Sign in to the Universal Search MCP server when no interactive terminal is
# available (for example from Claude Code's Bash tool).
#
#   mcp_login.sh start [server]   start `claude mcp login`, print the Google sign-in URL
#   mcp_login.sh check [server]   report whether that sign-in finished
#
# server defaults to workspace-universal.
#
# `claude mcp login` needs a terminal, so `start` runs it under `script` (a
# pseudo-terminal) in the background. It listens on localhost:$CALLBACK_PORT
# for Google's redirect; opening the printed URL in a browser on this machine
# and clicking Allow completes it. The listener gives up after 10 minutes.
#
# `start` revokes the server's existing token straight away, even if the new
# sign-in is never finished, and Google then revokes every other token issued
# to the same OAuth client (other Workspace MCP servers, other MCP clients).
# Only start when the token is expired or revoked (`mcp_status.sh --verify`).
#
# With MCP_SCOPE=local registrations, run it from the directory the server
# was registered for.

ACTION=$1
SERVER=${2:-workspace-universal}
LOG="${TMPDIR:-/tmp}/workspace-search-mcp-login-$USER-$SERVER.log"

case "$SERVER" in
    workspace-universal) ;;
    *) echo "Usage: $0 start|check [workspace-universal]"; exit 2 ;;
esac

case "$ACTION" in
    start)
        : > "$LOG"
        chmod 600 "$LOG"
        ( sleep 600 | BROWSER=/bin/true script -qfec "claude mcp login $SERVER" /dev/null ) >> "$LOG" 2>&1 &
        for _ in $(seq 1 30); do
            URL=$(grep -ao 'https://accounts.google.com/o/oauth2/v2/auth[^[:space:]]*' "$LOG" \
                | head -1 | sed 's/\x1b.*//' | tr -d '\a')
            [ -n "$URL" ] && break
            grep -q 'Authenticated with' "$LOG" && { echo "Already signed in: $SERVER"; exit 0; }
            sleep 1
        done
        if [ -z "$URL" ]; then
            echo "No sign-in URL after 30s. Log: $LOG"
            exit 1
        fi
        echo "$URL"
        ;;
    check)
        if grep -q "Authenticated with \"$SERVER\"" "$LOG" 2>/dev/null; then
            echo "Signed in: $SERVER"
            rm -f "$LOG"
        else
            echo "Not signed in yet: $SERVER"
            exit 1
        fi
        ;;
    *)
        echo "Usage: $0 start|check [workspace-universal]"
        exit 2
        ;;
esac
