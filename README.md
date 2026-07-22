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

## Stack

- Python 3.12+
- FastAPI
- Pydantic and pydantic-settings
- Pytest
- Codex CLI adapter for the first real meal-analysis provider

## Running the server

Requires Python 3.12 or newer. From the repository root, create and activate a virtual
environment, then install the project:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e ".[dev]"
```

Start the development server with the deterministic mock analyzer:

```powershell
uvicorn mosaic_server.main:app --reload --host 0.0.0.0 --port 8000
```

The health endpoint returns the active analyzer:

```json
{"status":"ok","meal_analyzer":"MockMealAnalyzer"}
```

## Configuration

Mosaic Server uses a typed `Settings` model from `pydantic-settings`. Configuration is
validated at startup instead of being read ad hoc throughout the code.

Sources are applied in this order:

1. Real process environment variables
2. A local `.env` file in the repository working directory
3. Defaults defined by the settings model

Environment variables therefore override `.env`. The `.env` file is intended for local
development only and is excluded from Git. Copy the committed template:

```powershell
Copy-Item .env.example .env
```

or on Linux:

```bash
cp .env.example .env
```

To use Codex locally, edit `.env`:

```dotenv
MOSAIC_MEAL_ANALYZER=codex
MOSAIC_CODEX_EXECUTABLE=codex
MOSAIC_CODEX_TIMEOUT_SECONDS=120
# MOSAIC_CODEX_MODEL=gpt-5.6-sol
```

On Windows, npm may expose Codex through a `.cmd` shim. When the server cannot find it,
set the full path returned by `where.exe codex`:

```dotenv
MOSAIC_CODEX_EXECUTABLE=C:\Users\your-user\AppData\Roaming\npm\codex.cmd
```

Restart the server after changing configuration. Settings are loaded once per process.

### Production recommendation

Do not commit a production `.env` file. On Ubuntu, inject the same `MOSAIC_*` variables
through the service manager. A practical systemd deployment can use a root-owned file
outside the repository:

```ini
# /etc/mosaic-server/mosaic-server.env
MOSAIC_MEAL_ANALYZER=codex
MOSAIC_CODEX_EXECUTABLE=/usr/local/bin/codex
MOSAIC_CODEX_TIMEOUT_SECONDS=120
```

Protect it:

```bash
sudo chown root:root /etc/mosaic-server/mosaic-server.env
sudo chmod 600 /etc/mosaic-server/mosaic-server.env
```

Reference it from the systemd unit:

```ini
[Service]
EnvironmentFile=/etc/mosaic-server/mosaic-server.env
```

This keeps deployment configuration outside Git while retaining the same validated settings
model. Future secrets such as API keys should preferably be supplied through a secret manager
or systemd credentials rather than stored in the repository's `.env` file.

## Installing Codex CLI on Ubuntu Server

### 1. Install Node.js and npm

```bash
sudo apt update
sudo apt install -y nodejs npm
```

Verify:

```bash
node --version
npm --version
```

If Ubuntu provides an old Node.js release, install a current LTS release using your preferred
Node.js version manager or package source.

### 2. Install and authenticate Codex CLI

```bash
sudo npm install -g @openai/codex
codex --version
which codex
codex --login
```

On a headless VPS, follow the terminal instructions and complete the sign-in in a browser on
another device. The Linux user running Mosaic Server must be the user that completes the Codex
login.

### 3. Install and run Mosaic Server

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e ".[dev]"
cp .env.example .env
```

For a quick manual test, set `MOSAIC_MEAL_ANALYZER=codex` in `.env` and run:

```bash
uvicorn mosaic_server.main:app --host 0.0.0.0 --port 8000
curl http://127.0.0.1:8000/health
```

Expected response:

```json
{"status":"ok","meal_analyzer":"CodexCliMealAnalyzer"}
```

If Codex is not found, compare `which codex` with `MOSAIC_CODEX_EXECUTABLE` and confirm that
the server process runs as the same authenticated user.

## Analyzer settings

- `MOSAIC_MEAL_ANALYZER` — `mock` or `codex`; defaults to `mock`
- `MOSAIC_CODEX_EXECUTABLE` — path or command name; defaults to `codex`
- `MOSAIC_CODEX_MODEL` — optional explicit model override
- `MOSAIC_CODEX_TIMEOUT_SECONDS` — validated range 1–900; defaults to `120`

The server writes each upload into a temporary private directory, invokes `codex exec` with
the image and a generated JSON schema, validates the final JSON with Pydantic, and deletes the
temporary files after the request. Provider failures are returned as HTTP 502 rather than being
silently replaced with fabricated nutrition data.

## Tests

```powershell
pytest
```

The tests use the mock analyzer and mock the Codex subprocess. They do not consume model usage
or require Codex authentication.

## Current API

- `GET /health`
- `POST /v1/meals/analyze`

Supported upload formats are JPEG, PNG, and WebP, with a maximum size of 10 MB.
