# Urdu Reading Annotation Platform (Phase 1 MVP)

A web platform for building human reference annotations for an EGRA-style Urdu reading assessment (LUMS DARE-RC, with the LUMS AI Hub).
Each 60-second recording of a Grade 2–3 child reading a passage aloud gets two independent annotations:
**Layer 1**, a verbatim Urdu transcript, and **Layer 2**, word-by-word correct/error scoring against the printed passage.
These annotations are the ground truth for checking whether ASR can replace human WCPM scoring.

## Prerequisites

- [uv](https://docs.astral.sh/uv/) for local development, or [Docker](https://docs.docker.com/get-docker/) with Compose v2

## Run locally without Docker

Only [uv](https://docs.astral.sh/uv/) is needed. Python, Postgres 16 (the `pgserver` wheel) and Node (the `nodejs-wheel` wheel) all come through uv, so nothing is installed system-wide.

```bash
uv run dev.py
```

The first run creates a local-only `.env` (admin password `admin`), a Postgres cluster in `.local/pgdata` on port 5433, `backend/.venv` and `frontend/node_modules`.
It then runs migrations and the admin seed, and starts the API on :8000 (or the next free port) and the UI on http://localhost:5173.
Press Ctrl+C to stop everything.

To run the tests, start only the database with `uv run dev.py db`, run `cd backend && uv run pytest`, then `uv run dev.py stop`.
Delete `.local/` to reset the database.

## Run with Docker (development)

```bash
cp .env.example .env
```

Edit `.env` and replace the four `CHANGE_ME` values:

| Variable | What to put |
| --- | --- |
| `POSTGRES_PASSWORD` | a strong database password |
| `DATABASE_URL` | the same database password, inside the URL |
| `SECRET_KEY` | output of `openssl rand -hex 32` (signs session cookies) |
| `ADMIN_PASSWORD` | the password for `ADMIN_EMAIL` |

Then start everything:

```bash
docker compose up --build
```

This starts three services:

- **postgres** (Postgres 16, initialised from the `.env` credentials)
- **api** (FastAPI on http://localhost:8000; runs migrations and creates the admin account on start)
- **web** (React UI on http://localhost:5173)

## Deploying to a server

For a step-by-step Google Cloud runbook (Console only), see [docs/deploy-gcp.md](docs/deploy-gcp.md).

Production uses `docker-compose.prod.yml`: Caddy serves the built UI over HTTPS and proxies `/api` to the API.
Postgres and the API are not reachable from outside, and a backup service writes nightly copies to `backups/`.

**Server:** Ubuntu 24.04 with Docker, 2 vCPU, 4 GB RAM, and disk for the audio (about 1 MB per 60-second recording).
Open only ports 22, 80 and 443. Point the domain's DNS A record at the server's IP before the first start.

```bash
git clone https://github.com/Basit-Rahim/Annotation_plateform.git /opt/annotation
cd /opt/annotation
cp .env.example .env
```

In `.env`, set `DOMAIN` and `ADMIN_EMAIL`, and generate `POSTGRES_PASSWORD`, `SECRET_KEY` and `ADMIN_PASSWORD`
with `openssl rand -hex 32`. Put the same database password inside `DATABASE_URL`, which keeps the host `postgres`.

```bash
docker compose -f docker-compose.prod.yml up -d --build
docker compose -f docker-compose.prod.yml ps        # all services running, api healthy
```

Migrations and the admin account are applied on every start. Caddy fetches the HTTPS certificate on the first request,
so give it a minute, then open `https://<DOMAIN>`.

**Updating:** `git pull`, then the same `up -d --build` command.

**Adding audio:** copy files into `/opt/annotation/data/incoming/` (for example with `scp` or SFTP), then use **Ingest audio**.

**Backups:** `backups/` holds a database dump (`db-*.dump`) and an audio archive (`audio-*.tar.gz`) per day,
kept for `BACKUP_KEEP_DAYS`. Copy them off the server regularly. To restore the database:

```bash
docker compose -f docker-compose.prod.yml exec -T postgres   pg_restore --clean --if-exists -U <POSTGRES_USER> -d <POSTGRES_DB> < backups/db-<stamp>.dump
```

**Logs:** `docker compose -f docker-compose.prod.yml logs -f api` (or `web`, `backup`).

## First-run flow

1. Open http://localhost:5173 and log in with `ADMIN_EMAIL` / `ADMIN_PASSWORD`.
2. **Passages**: create a passage (code such as `P01`, a title, and the Urdu text). It is split into numbered words on whitespace.
3. **Users**: create an annotator and tick Layer 1 and/or Layer 2 eligibility.
4. Copy audio into `data/incoming/` (see below), open **Ingest audio**, click **Scan folder**, then **Ingest** a file and fill in its metadata.
   The file moves to `data/audio/{recording_id}.{ext}`, and one Layer 1 task and one Layer 2 task enter the pool.
5. Log out and log in as the annotator. Click **Take next Layer 1** or **Take next Layer 2**.
6. Back as admin, **Export** downloads all submitted annotations as JSON, with Urdu text normalised (Annex E.4).

### Seeding test audio

Copy a few short `.wav` or `.mp3` files into `data/incoming/`. `.m4a`, `.ogg`, `.flac` and `.webm` also work.
`backend/tests/fixtures/sample.wav` is a 3-second tone you can use.

## How annotation works

- **Take next** assigns the oldest available task for that layer. Annotators can't browse or pick tasks.
- Each annotator can hold one task at a time. The lease runs for 120 minutes (`LEASE_DURATION_MINUTES`) after the last edit,
  so it never runs out while someone is working. A background job returns expired leases to the pool every minute.
- **Work in progress is always saved**, in both layers: to the browser on every change and to the server a moment later
  (status shown in the top bar). If the tab closes, the browser crashes or the connection drops, reopening the task restores it.
  If a lease lapses, the draft is kept and **Take next** gives that annotator their unfinished task back first.
- **Submit** saves the annotation. **Release** returns the task to the pool and discards the saved draft.
- Both workspaces have a waveform with three draggable marks: first word (green), last word (red) and the 60 s boundary (blue).
  The buttons under the waveform place each mark at the playhead.
- **Layer 1**: a right-to-left Nastaliq editor with buttons that insert `[unintelligible]`, `[non-target speech]` and `[code-switch]`.
- **Layer 2**: one row per printed word, with a Correct/Error chip and the closed Annex E.1 error-tag list.
  Use **+ Insert word here** between rows to record words the child added (INS).
- An admin can withdraw a recording from the Dashboard. This deletes the audio, cancels its tasks, and excludes it from exports.
- An admin can also **delete** a recording from the Dashboard. This removes it completely: audio, tasks, drafts and
  annotations (a recording with submitted annotations asks for a second confirmation). Use it for mistaken ingests.
- A passage can be deleted from **Passages** only while no recording uses it.

## Running the tests

Tests need the Postgres from the compose stack, because the pool relies on `SELECT … FOR UPDATE SKIP LOCKED` and a partial unique index.
They create and use a separate `<POSTGRES_DB>_test` database.

Inside Docker:

```bash
docker compose exec api pytest
```

Or on your machine, with Postgres running (`docker compose up -d postgres`):

```bash
cd backend
python -m venv .venv && . .venv/bin/activate     # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
pytest
```

When run on your machine, the tests read the database settings from the repository's `.env` and connect through `localhost:5432`.
Set `TEST_DATABASE_URL` to use a different database.

## Project layout

```
backend/    FastAPI app (app/), Alembic migrations, pytest suite
frontend/   React + TypeScript + Vite UI; Noto Nastaliq Urdu is bundled in src/fonts/
data/       incoming/ (drop folder) and audio/ (stored recordings); not committed
```

The bundled font is Noto Nastaliq Urdu (SIL Open Font License, see `frontend/src/fonts/OFL.txt`).
It is served by the app itself, never from a CDN.

## Phase 2 (not in this MVP)

- **Kobo integration is Phase 2.** In the MVP, audio comes only from the `data/incoming/` drop folder.
- **Forced alignment is Phase 2.** Layer 2 teachers scrub the audio manually, with no word-level highlighting.
- Also deferred: double annotation per layer, adjudication, IAA dashboards, pause/report flows, and password self-service.
