# Urdu Reading Annotation Platform (Phase 1 MVP)

A web platform for building human reference annotations for an EGRA-style Urdu reading assessment (LUMS DARE-RC, with the LUMS AI Hub).
Each 60-second recording of a Grade 2–3 child reading a passage aloud gets two independent annotations:
**Layer 1**, a verbatim Urdu transcript, and **Layer 2**, word-by-word correct/error scoring against the printed passage.
These annotations are the ground truth for checking whether ASR can replace human WCPM scoring.

## Prerequisites

- [Docker Desktop](https://www.docker.com/products/docker-desktop/) (with Docker Compose v2)
- Python 3.11+ and Node 20+ only if you want to run tests or develop outside Docker

## Setup

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
- Each annotator can hold one task at a time. The task is leased for 120 minutes (`LEASE_DURATION_MINUTES`).
  A background job returns expired leases to the pool every minute.
- **Submit** saves the annotation. **Release** returns the task to the pool and discards the draft.
- Both workspaces have a waveform with three draggable marks: first word (green), last word (red) and the 60 s boundary (blue).
  The buttons under the waveform place each mark at the playhead.
- **Layer 1**: a right-to-left Nastaliq editor with buttons that insert `[unintelligible]`, `[non-target speech]` and `[code-switch]`.
  The draft autosaves to the browser every 5 seconds and is restored if you reopen the same task.
- **Layer 2**: one row per printed word, with a Correct/Error chip and the closed Annex E.1 error-tag list.
  Use **+ Insert word here** between rows to record words the child added (INS).
- An admin can withdraw a recording from the Dashboard. This deletes the audio, cancels its tasks, and excludes it from exports.

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
