# Convenience wrapper around deploy.sh and the local dev/test workflow.
# Requires GNU Make (on Windows: Git Bash + `make`, WSL, or via choco/scoop).
#
# Usage:
#   make help          # list targets (default)
#   make install       # deps to run main.py locally
#   make install-dev   # + pytest, for running the test suite
#   make run           # start the local agent server on :8080
#   make test          # offline unit tests (no AWS calls)
#   make test-live      # opt-in live tests (real Bedrock calls, costs tokens)
#   make deploy-dry-run # preview the AgentCore deploy - no AWS changes
#   make deploy-diff    # show the CloudFormation diff - read-only
#   make deploy         # scaffold + deploy for real - provisions billed AWS resources
#   make teardown       # remove the deployed runtime from AWS

.PHONY: help install install-dev run test test-live deploy-dry-run deploy-diff deploy teardown clean

help:
	@echo "Targets:"
	@echo "  install        install deps to run main.py locally"
	@echo "  install-dev    install-dev + pytest for the test suite"
	@echo "  run            start the local agent server (python main.py, :8080)"
	@echo "  test           offline unit tests - no AWS calls"
	@echo "  test-live      opt-in live tests - real Bedrock calls, costs tokens"
	@echo "  deploy-dry-run preview the AgentCore deploy - no AWS changes"
	@echo "  deploy-diff    show the CloudFormation diff - read-only"
	@echo "  deploy         scaffold + deploy for real - provisions billed AWS resources"
	@echo "  teardown       remove the deployed runtime from AWS"
	@echo "  clean          remove __pycache__ / .pytest_cache"

install:
	pip install -r requirements-deploy.txt

install-dev:
	pip install -r requirements-dev.txt

run:
	python main.py

test:
	pytest

test-live:
	RUN_LIVE_TESTS=1 pytest tests/test_live_agent.py -v

deploy-dry-run:
	./deploy.sh --dry-run

deploy-diff:
	./deploy.sh --diff

deploy:
	./deploy.sh

teardown:
	./deploy.sh --teardown

clean:
	find . -name '__pycache__' -not -path './agentcore-project/*' -exec rm -rf {} +
	rm -rf .pytest_cache
