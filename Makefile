# Workspace Search MCP: common tasks. `make help` lists them.

Q ?= meeting

.PHONY: help test test-live probe status verify search search-json e2e setup login validate

help:  ## list targets
	@grep -E '^[a-z0-9-]+:.*## ' $(MAKEFILE_LIST) | awk -F':.*## ' '{printf "  make %-12s %s\n", $$1, $$2}'
	@echo "  Q=\"words\" sets the query for search, search-json and e2e (default: $(Q))"

test:  ## offline suite: syntax, shellcheck, unit, consistency, scripts, plugin validate
	@tests/run.sh

test-live:  ## offline suite + probe + status + end-to-end (needs a sign-in)
	@tests/run.sh --live

probe:  ## server versions, tool schema and scopes, no credentials
	@./mcp_probe.sh

status:  ## registered, token held, minutes left
	@./mcp_status.sh

verify:  ## ask Google whether the token is accepted and which corpora it covers
	@./mcp_status.sh --verify

search:  ## search_corpus directly: counts per corpus, then one line per result
	@./mcp_search.sh "$(Q)"

search-json:  ## search_corpus directly: counts as JSON
	@./mcp_search.sh "$(Q)" --json

e2e:  ## read-only end-to-end test: direct call, then a headless Claude Code session
	@./mcp_test.sh "$(Q)"

setup:  ## register workspace-universal with Claude Code
	@./claude_setup.sh

login:  ## sign in (only when verify says expired, revoked or none)
	@claude mcp login workspace-universal

validate:  ## validate the marketplace and plugin manifests
	@claude plugin validate . && claude plugin validate plugin
