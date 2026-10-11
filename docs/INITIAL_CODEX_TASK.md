# Copy the following prompt into Codex

Please read `AGENTS.md`, `README_CODEX_START_HERE.md`, `docs/Adex_Product_Technical_Design_v4.1.md`, `docs/PHASE1_BACKLOG.md`, and `docs/ACCEPTANCE.md`.

Implement **M00 only**. First output a dependency graph and list any contradictions in the docs; obey the v4.1 frozen ADRs. Then create an actual runnable Monorepo skeleton (not pseudo-files): Java 21 Spring Boot App and Automation; Python FastAPI Agent and Tools; Vite React web and Capacitor iOS project; versioned OpenAPI schemas; dev Docker Compose for PostgreSQL, Redis, Elasticsearch with private networks/volumes PLUS App LocalFileStorage bind mount (no OSS/MinIO), file metadata stub and controlled local upload/read API contract; health endpoints; service-specific migrations; .env.example without secrets; Makefile developer commands; CI running basic tests. Independently build each backend service image and start with Compose profiles. Run every stated command and report exact evidence. Do not connect any production credentials or do destructive database operations. If dependencies outside the repo cannot be obtained, mark them as blockers; do not pretend tests passed.

After M00 is reviewed, implement M01 in a new prompt/PR; do not start M01 automatically.
