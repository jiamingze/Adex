JAVA_HOME ?= /opt/homebrew/opt/openjdk@21/libexec/openjdk.jdk/Contents/Home
MAVEN_OPTS ?= -Djava.net.preferIPv4Stack=true
export MAVEN_OPTS
export JAVA_HOME
export PATH := $(JAVA_HOME)/bin:$(PATH)
.PHONY: doctor setup build test test-contract up-dev down-dev status test-integration

doctor:
	python3 scripts/doctor.py
setup:
	uv sync --python 3.12
	uv sync --project services/adex-agent --python 3.12
	uv sync --project services/adex-tools --python 3.12
	uv run --project services/adex-tools playwright install chromium
	pnpm install
	pnpm generate:contracts
build:
	mvn -B package
	pnpm --dir apps/web build
test:
	mvn -B test
	uv run --project services/adex-agent pytest services/adex-agent/tests -q
	uv run --project services/adex-tools pytest services/adex-tools/tests -q
	$(MAKE) test-contract
test-contract:
	uv run python scripts/check_contract.py
up-dev:
	python3 scripts/local_infra.py
	uv run python scripts/migrate.py
	uv run python scripts/dev.py start
down-dev:
	uv run python scripts/dev.py stop
status:
	uv run python scripts/dev.py status
test-integration:
	uv run python scripts/test_stack.py
