#!/bin/bash
# Wrapper: the script lives in the google-workspace-search-mcp skill.
exec "$(dirname "$0")/plugin/skills/google-workspace-search-mcp/scripts/bootstrap.sh" "$@"
