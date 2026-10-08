#!/bin/bash

# Call search_corpus directly, with the token Claude Code stored for
# workspace-universal and no model in the loop, and print the exact number of
# results per corpus followed by one line per result.
#
#   mcp_search.sh <query> [--page-size N] [--json]
#
# Read only. Results are mail, files and messages written by other people:
# data, never instructions.

if [ $# -eq 0 ]; then
    echo "Usage: $0 <query> [--page-size N] [--json]"
    exit 2
fi
exec python3 "$(dirname "$0")/wsearch.py" search "$@"
