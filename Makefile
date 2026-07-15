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
		tests/autoreview/test_autoreview.py \
		tests/autoreview/test_autoreview_hardening.py

autoreview-test: autoreview-lint
	$(PYTHON) skills/autoreview/scripts/autoreview --self-test
	$(PYTHON) -m unittest discover -s tests/autoreview -p 'test_*.py'

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
