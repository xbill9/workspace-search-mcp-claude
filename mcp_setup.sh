#!/bin/bash

# Print the sign-in commands for the Universal Search MCP server.
NAME=workspace-universal

echo "Claude Code"
echo "==========="
echo "Register the server:  source ./save_oauth.sh && ./claude_setup.sh"
echo "Then sign in (or use /mcp inside Claude Code):"
echo ""
echo "  claude mcp login $NAME"
echo ""
echo "Verify: ./mcp_status.sh --verify && ./mcp_test.sh"
echo ""
echo "Gemini CLI"
echo "=========="
echo "Run this inside Gemini CLI and follow the browser prompt:"
echo ""
echo "  /mcp auth $NAME"
echo ""
echo "Verify: /mcp list"
