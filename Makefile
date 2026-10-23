# Respect setup-java / user JAVA_HOME. Fall back to Homebrew only when it exists;
# Linux Java installations work through PATH without a macOS-only JAVA_HOME.
ifeq ($(origin JAVA_HOME),undefined)
ifneq ($(wildcard /opt/homebrew/opt/openjdk@21/libexec/openjdk.jdk/Contents/Home),)
JAVA_HOME := /opt/homebrew/opt/openjdk@21/libexec/openjdk.jdk/Contents/Home
endif
endif
MAVEN_OPTS ?= -Djava.net.preferIPv4Stack=true
export MAVEN_OPTS
ifneq ($(strip $(JAVA_HOME)),)
export JAVA_HOME
export PATH := $(JAVA_HOME)/bin:$(PATH)
endif
.PHONY: doctor setup build test test-contract up-dev down-dev status test-integration format check-style test-client

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
test-client:
	node scripts/test_client.mjs

test:
	uv run pytest tests/scripts -q
	$(MAKE) test-client
	uv run python scripts/check_architecture.py
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

format:
	mvn -B com.diffplug.spotless:spotless-maven-plugin:2.44.3:apply
	uv run ruff format services/adex-agent/src services/adex-tools/src

check-style:
	mvn -B com.diffplug.spotless:spotless-maven-plugin:2.44.3:check
	uv run ruff format --check services/adex-agent/src services/adex-tools/src
	uv run python scripts/check_architecture.py

# Synthetic UI only: no Java, database, model keys, Xcode or external execution.
.PHONY: demo-ui
demo-ui:
	pnpm install --frozen-lockfile
	pnpm --dir apps/web build
	uv run python tests/fixtures/product_gallery_server.py

# macOS native speech lifecycle regression, independent of microphone permissions.
.PHONY: test-ios-speech
test-ios-speech:
	mkdir -p .local-data/native-tests
	swiftc apps/ios/ios/App/CapApp-SPM/Sources/CapApp-SPM/SpeechGestureGate.swift tests/swift/SpeechGestureGate/main.swift -o .local-data/native-tests/speech-gesture
	.local-data/native-tests/speech-gesture

.PHONY: test-ios-speech-stream
test-ios-speech-stream:
	mkdir -p .local-data/native-tests
	swiftc apps/ios/ios/App/CapApp-SPM/Sources/CapApp-SPM/SpeechStream.swift tests/swift/SpeechStream/main.swift -o .local-data/native-tests/speech-stream
	.local-data/native-tests/speech-stream

.PHONY: test-ios-speech-choice
test-ios-speech-choice:
	mkdir -p .local-data/native-tests
	swiftc apps/ios/ios/App/CapApp-SPM/Sources/CapApp-SPM/SpeechTranscriptChoice.swift tests/swift/SpeechTranscriptChoice/main.swift -o .local-data/native-tests/speech-choice
	.local-data/native-tests/speech-choice
