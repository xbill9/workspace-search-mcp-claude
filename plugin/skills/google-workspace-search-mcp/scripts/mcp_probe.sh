#!/bin/bash

# Probe the Universal Search MCP server without credentials and report the
# spec versions it advertises (server/discover, MCP 2026-07-28), the version
# it negotiates over a legacy initialize (2025-11-25), its tools and their
# arguments, and the scopes in its OAuth protected resource metadata, grouped
# by corpus. All counting happens in wsearch.py.

exec python3 "$(dirname "$0")/wsearch.py" probe
