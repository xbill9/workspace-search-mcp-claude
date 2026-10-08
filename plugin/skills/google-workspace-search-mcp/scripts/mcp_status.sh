#!/bin/bash

# Sign-in status of workspace-universal in Claude Code.
#
#   mcp_status.sh [--verify]
#
# Whether the server is registered for this directory (from `claude mcp list`),
# whether Claude Code holds a token for it, minutes until it expires, and
# whether a refresh token exists. Token values are never printed.
#
# --verify also asks Google (oauth2.googleapis.com/tokeninfo) whether the token
# is still accepted and which scopes it carries, and reports the corpora
# (gmail, drive, calendar, chat) search_corpus can search with them. A token
# can be revoked before it expires, for example when another server or MCP
# client signs in again through the same OAuth client.

LIST=$(claude mcp list 2>&1)
exec python3 "$(dirname "$0")/wsearch.py" status "$LIST" "$@"
