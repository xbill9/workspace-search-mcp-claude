#!/bin/bash

# Register Google's Universal Search MCP server for Workspace with Claude Code.
#
# Claude Code keeps the OAuth client secret in its credential store, never in
# .mcp.json, so the server is added with `claude mcp add-json --client-secret`
# rather than from a checked-in config file.
#
# Environment (all optional):
#   CLIENT_ID, CLIENT_SECRET  OAuth web client (default: ~/client_id.txt, ~/client_secret.txt)
#   CALLBACK_PORT             local OAuth callback port (default: 8765)
#   MCP_SCOPE                 user | local | project (default: user)
#   CORPORA                   which products search_corpus may search
#                             (default: "gmail drive calendar chat")
#
# The server searches only the products whose scope the sign-in grants, so
# CORPORA decides what search_corpus can return.
#
# The OAuth client must list http://localhost:$CALLBACK_PORT/callback
# under Authorized redirect URIs.

if ! command -v claude > /dev/null 2>&1; then
    echo "Error: claude (Claude Code) not found on PATH."
    exit 1
fi

CLIENT_ID=${CLIENT_ID:-$(cat "$HOME/client_id.txt" 2>/dev/null)}
CLIENT_SECRET=${CLIENT_SECRET:-$(cat "$HOME/client_secret.txt" 2>/dev/null)}
CALLBACK_PORT=${CALLBACK_PORT:-8765}
MCP_SCOPE=${MCP_SCOPE:-user}
CORPORA=${CORPORA:-gmail drive calendar chat}

if [ -z "$CLIENT_ID" ] || [ -z "$CLIENT_SECRET" ]; then
    echo "Error: OAuth client not set. Run 'source ./save_oauth.sh' first."
    exit 1
fi

NAME=workspace-universal
URL=https://workspacemcp.googleapis.com/mcp/v1
G=https://www.googleapis.com/auth

# corpus -> scope (developers.google.com/workspace/guides/universal-search-mcp)
SCOPES=""
for c in $CORPORA; do
    case "$c" in
        gmail)    SCOPES="$SCOPES $G/gmail.readonly" ;;
        drive)    SCOPES="$SCOPES $G/drive.readonly" ;;
        calendar) SCOPES="$SCOPES $G/calendar.readonly" ;;
        chat)     SCOPES="$SCOPES $G/chat.messages.readonly" ;;
        *) echo "Error: unknown corpus '$c' (use gmail, drive, calendar, chat)."; exit 1 ;;
    esac
done
SCOPES=${SCOPES# }
if [ -z "$SCOPES" ]; then
    echo "Error: CORPORA is empty."
    exit 1
fi

echo "Adding $NAME to Claude Code (scope: $MCP_SCOPE, corpora: $CORPORA)"
echo "Redirect URI required on the OAuth client: http://localhost:$CALLBACK_PORT/callback"
echo ""

JSON=$(printf '{"type":"http","url":"%s","oauth":{"clientId":"%s","callbackPort":%s,"scopes":"%s"}}' \
    "$URL" "$CLIENT_ID" "$CALLBACK_PORT" "$SCOPES")
claude mcp remove "$NAME" -s "$MCP_SCOPE" > /dev/null 2>&1
MCP_CLIENT_SECRET="$CLIENT_SECRET" claude mcp add-json --client-secret -s "$MCP_SCOPE" "$NAME" "$JSON" || exit 1

# Workspace developer docs server: public, no OAuth
claude mcp remove workspace-developer -s "$MCP_SCOPE" > /dev/null 2>&1
claude mcp add --transport http -s "$MCP_SCOPE" workspace-developer https://workspace-developer.goog/mcp

echo ""
echo "Next: sign in, either inside Claude Code with /mcp, or from the shell:"
echo ""
echo "  claude mcp login $NAME"
echo ""
echo "Then check with: ./mcp_status.sh --verify"
