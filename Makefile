SHELL := /bin/bash
PYTHON ?= python3
TEST_PATTERN ?=

.PHONY: lint test test-integration \
	autoreview-lint autoreview-test \
	kindctl-lint kindctl-test kindctl-test-integration

lint: autoreview-lint kindctl-lint

test: autoreview-test kindctl-test

test-integration: kindctl-test-integration

autoreview-lint:
	bash -n skills/autoreview/scripts/test-review-harness
	$(PYTHON) -m py_compile \
		skills/autoreview/scripts/autoreview \
		skills/autoreview/scripts/test-review-harness.py \
		skills/autoreview/scripts/autoreview_test.py
	@if command -v shellcheck >/dev/null 2>&1; then shellcheck skills/autoreview/scripts/test-review-harness; else echo "shellcheck not installed; skipping"; fi

autoreview-test: autoreview-lint
	$(PYTHON) skills/autoreview/scripts/autoreview --self-test-config-defaults
	$(PYTHON) skills/autoreview/scripts/autoreview --self-test-fallback-scope
	$(PYTHON) skills/autoreview/scripts/autoreview --self-test-engine-isolation
	$(PYTHON) skills/autoreview/scripts/autoreview --self-test-heartbeat-metrics
	$(PYTHON) skills/autoreview/scripts/autoreview --self-test-json-array-parser
	$(PYTHON) skills/autoreview/scripts/autoreview --self-test-opencode-jsonl-parser
	$(PYTHON) skills/autoreview/scripts/autoreview --self-test-opencode-isolation
	$(PYTHON) skills/autoreview/scripts/autoreview --self-test-cursor-jsonl-parser
	$(PYTHON) -m unittest \
		skills/autoreview/scripts/autoreview_test.py \
		skills.autoreview.tests.test_autoreview_hardening

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
