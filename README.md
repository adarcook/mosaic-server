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
- Pydantic
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

## Installing Codex CLI on Ubuntu Server

### 1. Install Node.js and npm

Install the Ubuntu packages first:

```bash
sudo apt update
sudo apt install -y nodejs npm
```

Verify the installation:

```bash
node --version
npm --version
```

If the Ubuntu repository provides an old Node.js release, install a current LTS release
using your preferred Node.js version manager or package source before continuing.

### 2. Install Codex CLI

```bash
sudo npm install -g @openai/codex
```

Verify that the command is available:

```bash
codex --version
which codex
```

### 3. Sign in with ChatGPT

Run:

```bash
codex --login
```

Follow the authorization instructions shown in the terminal. On a headless VPS, open the
provided sign-in address in a browser on another device when prompted, then complete the
ChatGPT sign-in flow.

Confirm that authentication works:

```bash
codex
```

Exit the interactive session with `Ctrl+C` after the prompt opens successfully.

To refresh an existing or expired login:

```bash
codex logout
codex --login
```

### 4. Install Mosaic Server on Ubuntu

From the repository root:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e ".[dev]"
```

### 5. Enable the Codex meal analyzer

```bash
export MOSAIC_MEAL_ANALYZER=codex
export MOSAIC_CODEX_TIMEOUT_SECONDS=120
uvicorn mosaic_server.main:app --host 0.0.0.0 --port 8000
```

Check the active analyzer:

```bash
curl http://127.0.0.1:8000/health
```

Expected response:

```json
{"status":"ok","meal_analyzer":"CodexCliMealAnalyzer"}
```

### Ubuntu troubleshooting

If `codex` is not found after installation:

```bash
npm config get prefix
which npm
which codex
```

Make sure the npm global binary directory is included in the `PATH` of the Linux user that
runs Mosaic Server. The same user must also complete `codex --login`; authentication stored
for another user, including `root`, will not automatically be available to the service user.

## Enabling real analysis with Codex CLI

Install and authenticate a current Codex CLI release on the machine running the server.
Then set the analyzer provider before starting Uvicorn.

PowerShell:

```powershell
$env:MOSAIC_MEAL_ANALYZER="codex"
$env:MOSAIC_CODEX_TIMEOUT_SECONDS="120"
$env:MOSAIC_CODEX_EXECUTABLE="C:\Users\orele\AppData\Roaming\npm\codex.cmd"
uvicorn mosaic_server.main:app --reload --host 0.0.0.0 --port 8000
```

Linux/VPS:

```bash
export MOSAIC_MEAL_ANALYZER=codex
export MOSAIC_CODEX_TIMEOUT_SECONDS=120
uvicorn mosaic_server.main:app --reload --host 0.0.0.0 --port 8000
```

Optional settings:

- `MOSAIC_CODEX_EXECUTABLE` — path or command name for Codex CLI; defaults to `codex`
- `MOSAIC_CODEX_MODEL` — explicit model override; omitted by default
- `MOSAIC_CODEX_TIMEOUT_SECONDS` — process timeout; defaults to `120`

The server writes each upload into a temporary private directory, invokes `codex exec`
with the image and a generated JSON schema, validates the final JSON with Pydantic, and
deletes the temporary files after the request. Provider failures are returned as HTTP 502
rather than being silently replaced with fabricated nutrition data.

## Tests

```powershell
pytest
```

The tests use the mock analyzer and mock the Codex subprocess. They do not consume model
usage or require Codex authentication.

## Current API

- `GET /health`
- `POST /v1/meals/analyze`

Supported upload formats are JPEG, PNG, and WebP, with a maximum size of 10 MB.
