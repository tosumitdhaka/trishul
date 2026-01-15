# Trishul — FCAPS Utilities Tool

[![Python](https://img.shields.io/badge/python-%3E%3D3.8-blue)](https://www.python.org/) [![FastAPI](https://img.shields.io/badge/fastapi-%3E%3D0.100.0-brightgreen)](https://fastapi.tiangolo.com/) [![Status](https://img.shields.io/badge/status-active-green)](#)

Trishul is a cloud-native toolkit for FCAPS engineers providing compact, high-impact utilities for parsing, collecting, analyzing and visualizing network and device telemetry. It bundles multiple focused components—MIB parsing, SNMP trap sender/receiver, SNMP walks, protobuf decoding, data exports and lightweight web APIs—designed to be run in containers and integrated into modern observability stacks (Prometheus / Grafana).

This README is tailored to the repository layout and core entrypoints (for example `backend/main.py` and `core/parser.py`).

Table of contents
- Overview
- Key components
- Architecture & cloud-native design
- Quickstart (local)
- Quickstart (Docker)
- Running in Kubernetes / Helm
- Configuration
- Usage examples
  - MIB parsing
  - SNMP walk
  - SNMP trap sender / receiver
  - Protobuf decoding
- Monitoring & observability
- Project layout
- Development & tests
- Roadmap
- Contributing
- Security
- Contact

Overview
--------
Trishul targets FCAPS workflows by providing small, focused utilities that are easy to compose and operate at scale. It is intentionally modular so operators can run just the components they need, or the entire stack in a cloud-native environment.

Key components
--------------
- MIB Parser (core/parser.py)
  - Fast, thread-safe MIB compilation and parsing using pysmi/pysnmp
  - Batch enrichment of Textual Conventions (TCs), notifications, parents, enumerations
  - Caching, deduplication and async wrappers for web integration
- SNMP Trap Receiver
  - HTTP/WebSocket integration for job notifications and UI updates (backend WebSocket manager)
  - Endpoints and services to receive traps and convert into parsed records or alerts
- SNMP Trap Sender
  - Utilities to generate and send SNMP traps for testing/alerting workflows
- SNMP Walks (backend/services/snmp_walk_service.py)
  - Walk devices, collect OIDs and store/export results
  - Integrates with job service and WebSocket notifications
- Protobuf Decoder (core/protobuf_decoder.py)
  - Decode telemetry payloads encoded with protobuf (supports grpc/tools & google protos)
- Upload / Export / Metrics services
  - UploadService, ExportService, JobService in backend to manage files, exports and long-running jobs
- Monitoring & Visualization integrations
  - Prometheus client metrics are included; exposes metrics for scraping
  - Designed to pair with Prometheus + Grafana for dashboards and alerting

Cloud-native & architecture
---------------------------
Trishul is built to run in containers and orchestrators:
- Container-friendly processes (FastAPI + Uvicorn, background services)
- Filesystem layout that allows compiled MIBs, exports and logs to be mounted as persistent volumes
- Helm charts under `helm/` (if present) for Kubernetes deployment
- Metrics endpoint compatible with Prometheus; use sidecars or scrape configs to collect metrics
- Designed for horizontal scaling: stateless API + external database for shared data

Quickstart — Local (development)
--------------------------------
Prerequisites
- Python 3.8+
- pip
- (Optional) Node.js 14+ for frontend dev

Clone and install
    git clone https://github.com/tosumitdhaka/trishul.git
    cd trishul

    python -m venv .venv
    source .venv/bin/activate
    pip install -r requirements.txt

Run backend (dev)
    python backend/main.py

or using uvicorn
    uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload

After startup, the server prints key endpoints (frontend, docs and health). Open API docs at /docs.

Quickstart — Docker
-------------------
Build and run (example):
    docker build -t trishul:latest -f docker/Dockerfile .
    docker run -e CONFIG__ENV=production -p 8000:8000 trishul:latest

If you use docker-compose in your environment, mount directories for compiled MIBs and exports and connect to your database.

Kubernetes / Helm
-----------------
- Use the `helm/` chart (when present) to deploy to a cluster. Ensure to configure:
  - PersistentVolumeClaims for compiled MIBs and exports
  - Secrets for DB credentials and any SNMP community strings / keys
  - Prometheus scrape annotations for metrics

Configuration
-------------
The app loads runtime configuration via `services/config_service.py` and `config/` examples. Key config sections:
- web: host, port, api_v1_prefix, cors_origins
- parser: compiled_dir, mib_search_dirs, deduplication_enabled, force_compile
- cache: enabled, directory
- database: SQLAlchemy / MySQL connection
- logging: level

Usage examples
--------------
MIB parsing (Python API)

```python
from services.config_service import Config
from core.parser import MibParser

cfg = Config()
parser = MibParser(cfg)
df = parser.parse_file('/path/to/IF-MIB.mib')
print(df.head())
```

Parse uploaded MIB content (useful for web UI uploads):

```python
content = open('IF-MIB.mib').read()
df = parser.parse_from_content(content, filename='IF-MIB.mib')
```

SNMP walk (example using SNMPWalkService)
- The service is wired into backend and can be invoked via the job API. It will perform walks and stream progress over WebSockets.

SNMP trap receiver & sender
- The repo includes utilities and endpoints to receive and emit traps; these integrate with job and export services. Use the `backend` APIs (see `backend/api/v1`) for concrete routes.

Protobuf decoding
- Use the Protobuf decoder utilities to decode binary telemetry payloads; see `core/protobuf_decoder.py` for supported helpers and example usage.

Monitoring & observability
--------------------------
- The application exposes Prometheus metrics (prometheus-client). Example metrics available:
  - job counts, parsing times, compilation stats, cache hits/misses
- Best practice: deploy Prometheus to scrape /metrics and add Grafana dashboards for:
  - MIB parsing throughput and errors
  - SNMP walk job durations
  - Trap receive rate and processing latency
- Alerting: configure Prometheus Alertmanager rules for critical errors (e.g., database connectivity, repeated parse failures)

Project layout (high level)
--------------------------
- backend/        — FastAPI app, API routers, services and entrypoint (`backend/main.py`)
- core/           — Core parsing, deduplication, protobuf decoding and file utilities
- services/       — Shared services (config, small helpers)
- frontend/       — Optional UI assets (served statically if present)
- docker/         — Dockerfile(s) and container helpers
- helm/           — Helm charts for Kubernetes
- tests/          — Unit & integration tests
- requirements.txt — Python dependencies

Development & tests
-------------------
- Use the virtualenv and run `pip install -r requirements.txt`.
- Run tests:
    pytest -q
- Lint/format: black, flake8, eslint/prettier for frontend

Roadmap
-------
Planned additions and improvements (examples):
- RBAC and authentication for API/UI
- Additional telemetry decoders (e.g., JSON/CEF, NetFlow)
- Prometheus exporters for per-tenant metrics
- ML anomaly detection service for faults/performance
- Multi-tenant accounting & billing export modules

Contributing
------------
Contributions are welcome. Suggested workflow:
1. Fork and create a feature branch: `git checkout -b feat/your-feature`
2. Implement changes and add tests
3. Run tests: `pytest`
4. Open a pull request with a clear description and test coverage

Security
--------
- Do not commit secrets. Use environment variables or a secrets manager
- Sanitize and validate device input and uploads
- Add authentication and network-level restrictions before exposing services to production

Contact
-------
- Repository: https://github.com/tosumitdhaka/trishul
- Maintainer: tosumitdhaka (GitHub)
- For questions or help, open an issue in the repository

---

Notes
-----
This update focuses on capturing the full scope of Trishul: MIB parser, SNMP trap sender/receiver, SNMP walks, protobuf decoding, export and metrics integrations, and cloud-native deployment. If you want, I can:
- Add example curl commands for API endpoints after scanning `backend/api/v1` routes,
- Add a sample docker-compose for local multi-service runs,
- Add Prometheus scrape snippets and a basic Grafana dashboard JSON,
- Or split README into README.md + docs/* and create a docs index.