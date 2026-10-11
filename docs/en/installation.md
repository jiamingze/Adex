# Installation

[中文](../zh-CN/installation.md) · [README](../../README.md)

## Choose an environment

Local development runs services directly and gives readable logs. Docker Compose runs the service topology in containers. iOS needs a working server plus macOS and full Xcode; the phone is a client, not a server.

## macOS prerequisites

Install Homebrew from its official site, then:

```bash
brew install openjdk@21 maven node@22 pnpm uv postgresql@16 redis ffmpeg
export JAVA_HOME="$(brew --prefix openjdk@21)/libexec/openjdk.jdk/Contents/Home"
export PATH="$JAVA_HOME/bin:$(brew --prefix node@22)/bin:$PATH"
```

Use pnpm 10 (the repository pins 10.11.0). Full Xcode is needed only for iOS. FFmpeg is used for media composition and fixtures. Docker Desktop or Colima is needed for isolated runners and container tests, not basic local chat.

## Ubuntu prerequisites

Use Java 21, Maven, Node.js 22, pnpm 10, uv, Python 3.12+, PostgreSQL 16, Redis, and FFmpeg. `scripts/local_infra.py` recognizes `/usr/lib/postgresql/16/bin`. Run the application as a normal user; PostgreSQL `initdb` refuses root. Consult each vendor's installation documentation for your distribution.

## Bootstrap and start

```bash
git clone https://github.com/jiamingze/Adex.git
cd Adex
make doctor
make setup
uv run python scripts/init_env.py
```

Edit `.env` before starting. Choose `ADEX_MODEL_PROVIDER=mock` for a provider-free demo or supply real keys using [configuration](configuration.md). Do not copy placeholder passwords from `.env.example` into a deployment: the initializer generates actual random credentials.

```bash
make build
make up-dev
make status
```

`up-dev` starts a project-local PostgreSQL cluster on 55432 and Redis on 56379, applies migrations, and launches App (8080), Automation (8081), Agent (8105), Tools (8107), and Web (5173). Runtime data lives in ignored `.local-data/`. Open http://127.0.0.1:5173.

`make down-dev` stops application processes. It does not delete persisted data or shut down infrastructure. After changing server code, rebuild and restart the affected services; rebuilding a JAR alone does not replace a running process.

## Docker Compose

Initialize `.env` first. Docker must have enough memory and disk for PostgreSQL, two JVM services, Python services, and any enabled runners/indexing.

```bash
docker compose --env-file .env -f deploy/compose/compose.yaml config --quiet
docker compose --env-file .env -f deploy/compose/compose.yaml up -d --build
```

Default Web binding is loopback port 5173. Optional Elasticsearch:

```bash
docker compose --env-file .env -f deploy/compose/compose.yaml --profile search up -d --build
```

The Compose configuration rewrites internal service addresses for its network. Persistent volumes and the file bind mount must be backed up together. For Linux hosting, set `ADEX_FILES_HOST_DIR` to a private persistent directory such as `/data/adex/files`; inspect the rendered Compose configuration before deployment. See [operations](../RUNBOOK.md).

## iOS

1. Install full Xcode and its iOS platform, accept its setup prompts, and connect your device.
2. Enable Developer Mode and trust the computer on the iPhone.
3. Expose the App gateway through reachable HTTPS. A phone's `localhost` points to the phone, not your Mac.
4. Build the bundled client:

```bash
ADEX_IOS_API_URL=https://your-gateway.example uv run python scripts/prepare_ios.py
open apps/ios/ios/App/App.xcodeproj
```

5. In Xcode, choose your bundle identifier and your own Personal Team under Signing & Capabilities. Select the device and run.

Free Personal Team signing typically needs renewal after seven days. Project-owned signing accounts/certificates are not distributed. Native permissions cover camera, selected photos, microphone, and speech recognition. Apple speech recognition may use network processing if local recognition is unavailable.

The bundled API URL is a build-time setting. Rebuild after changing it. Temporary tunnel URLs may expire and are less predictable than a stable HTTPS endpoint. `scripts/public_access.py` can create a development tunnel; it is not a managed production hosting service.

## Troubleshooting

| Symptom | Check |
| --- | --- |
| Missing dependency | `make doctor`; verify executable versions and JAVA_HOME |
| Database bootstrap fails | Port 55432, PostgreSQL 16 binaries, normal-user ownership of `.local-data/postgres` |
| Provider rejected | Key, model ID, region, entitlement and quota; do not assume chat access includes music/video |
| Phone cannot connect | Public HTTPS origin, gateway reachability, native CORS, tunnel lifetime and current bundled API URL |
| Upload times out | Connection, 25 MiB limit and storage quota; retry uses the same logical request key |
| Task waiting | `make status`, worker enabled, lease status; never bypass state with direct production DB edits |

Before sharing logs, redact keys, cookies, bearer tokens, media tickets, personal content and device identifiers.
