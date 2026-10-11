FROM docker:29-cli
RUN apk add --no-cache python3 && addgroup -g 10001 adex && adduser -D -u 10001 -G adex adex
WORKDIR /runner
COPY runners/gateway/server.py /runner/server.py
COPY services/adex-tools/src/adex_tools/code_runner.py /runner/code_runner.py
ENV ADEX_RUNNER_BIND=0.0.0.0 ADEX_CODE_RUNNER_MODE=docker PYTHONDONTWRITEBYTECODE=1
USER 10001:10001
ENTRYPOINT ["python3","/runner/server.py"]
