SHELL := /bin/bash
TEST_PATTERN ?=

.PHONY: lint test test-integration kindctl-lint kindctl-test kindctl-test-integration

lint: kindctl-lint

test: kindctl-test

test-integration: kindctl-test-integration

kindctl-lint:
	bash -n skills/kindctl/scripts/kindctl
	bash -n tests/kindctl/run-tests.sh
	bash -n tests/kindctl/run-integration.sh
	python3 tests/kindctl/lint-actions-pinned.py
	@if command -v shellcheck >/dev/null 2>&1; then shellcheck skills/kindctl/scripts/kindctl tests/kindctl/run-tests.sh tests/kindctl/run-integration.sh; else echo "shellcheck not installed; skipping"; fi

kindctl-test:
	TEST_PATTERN="$(TEST_PATTERN)" tests/kindctl/run-tests.sh

kindctl-test-integration:
	tests/kindctl/run-integration.sh
