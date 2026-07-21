# Mosaic Server

Always-on FastAPI service intended to run on the VPS.

## Responsibilities

- Authenticate Mosaic clients
- Receive meal photos and structured health data
- Orchestrate remote analysis through a replaceable analyzer adapter
- Validate requests and responses against `mosaic-contracts`
- Store operational data until Mosaic Core synchronizes it
- Expose health, synchronization, and analysis APIs

## Non-responsibilities

- Long-term personal intelligence and cross-domain reasoning
- Android user-interface logic
- Permanent coupling to Codex CLI or any single model provider

## Planned stack

- Python 3.12+
- FastAPI
- Pydantic
- SQLAlchemy
- PostgreSQL for production
- Docker

## Running the server

Requires Python 3.12 or newer. From the repository root, create and activate a virtual
environment, then install the project:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e .
```

Start the development server:

```powershell
uvicorn mosaic_server.main:app --reload --host 0.0.0.0 --port 8000
```

The API is available at `http://127.0.0.1:8000`. Verify it is running by opening
`http://127.0.0.1:8000/health`; the endpoint should return `{"status":"ok"}`.

## Proposed package layout

```text
src/mosaic_server/
├── api/
├── analyzers/
├── core/
├── db/
├── models/
└── services/
```

## Status

Foundation stage. The first implementation milestone is a health endpoint and a versioned meal-analysis contract.
