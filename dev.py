# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "pgserver==0.1.4",
#     "nodejs-wheel>=20,<21",
#     "python-dotenv>=1.0",
# ]
# ///
"""Run the whole stack on this machine without Docker: `uv run dev.py`.

Everything comes from uv: Postgres binaries (pgserver wheel), Node/npm
(nodejs-wheel) and the backend's Python environment (backend/.venv). Nothing
is installed system-wide. State lives in .local/ (database) and data/ (audio).

    uv run dev.py           start Postgres, API (:8000) and web UI (:5173)
    uv run dev.py db        start only Postgres (e.g. for `cd backend && uv run pytest`)
    uv run dev.py stop      stop a Postgres left running by `db`

Production still runs on Docker (docker-compose.yml); this is local dev only.
"""

import os
import secrets
import shutil
import signal
import socket
import subprocess
import sys
import time
from pathlib import Path
from urllib.parse import urlparse

from dotenv import dotenv_values
from pgserver._commands import POSTGRES_BIN_PATH

ROOT = Path(__file__).resolve().parent
BACKEND = ROOT / "backend"
FRONTEND = ROOT / "frontend"
LOCAL = ROOT / ".local"
PGDATA = LOCAL / "pgdata"
ENV_FILE = ROOT / ".env"
LOCAL_PG_PORT = 5433  # not 5432, so it never clashes with a Postgres you already run
EXE = ".exe" if os.name == "nt" else ""
# node/npm from nodejs-wheel live next to this script's interpreter.
NODE_BIN = Path(sys.executable).parent


def log(msg: str) -> None:
    print(f"\033[36m[dev]\033[0m {msg}", flush=True)


def pg(tool: str) -> str:
    return str(POSTGRES_BIN_PATH / f"{tool}{EXE}")


def ensure_env() -> dict[str, str]:
    """Create a local-only .env on first run; reuse whatever is there afterwards."""
    if not ENV_FILE.exists():
        db_password = secrets.token_hex(12)
        text = (ROOT / ".env.example").read_text(encoding="utf-8")
        replacements = {
            "POSTGRES_PASSWORD=": f"POSTGRES_PASSWORD={db_password}",
            "POSTGRES_HOST=": "POSTGRES_HOST=localhost",
            "POSTGRES_PORT=": f"POSTGRES_PORT={LOCAL_PG_PORT}",
            "DATABASE_URL=": f"DATABASE_URL=postgresql://urdu_annot:{db_password}@localhost:{LOCAL_PG_PORT}/urdu_annot",
            "SECRET_KEY=": f"SECRET_KEY={secrets.token_hex(32)}",
            "ADMIN_PASSWORD=": "ADMIN_PASSWORD=admin",
        }
        lines = []
        for line in text.splitlines():
            for prefix, new in replacements.items():
                if line.startswith(prefix):
                    line = new
            lines.append(line)
        ENV_FILE.write_text("\n".join(lines) + "\n", encoding="utf-8")
        log("created .env for local development (admin password: admin)")
    return {k: v for k, v in dotenv_values(ENV_FILE).items() if v is not None}


def pg_running() -> bool:
    return subprocess.run([pg("pg_ctl"), "-D", str(PGDATA), "status"], capture_output=True).returncode == 0


def start_postgres(env: dict[str, str]) -> None:
    url = urlparse(env["DATABASE_URL"])
    user, password, port, dbname = url.username, url.password or "", url.port or 5432, url.path.lstrip("/")

    if not (PGDATA / "PG_VERSION").exists():
        log("initialising local Postgres cluster in .local/pgdata")
        LOCAL.mkdir(exist_ok=True)
        pwfile = LOCAL / "pwfile"
        pwfile.write_text(password, encoding="utf-8")
        try:
            subprocess.run(
                [pg("initdb"), "-D", str(PGDATA), "-U", user, "--pwfile", str(pwfile),
                 "--auth=scram-sha-256", "--encoding=UTF8", "--locale=C"],
                check=True, capture_output=True,
            )
        finally:
            pwfile.unlink(missing_ok=True)

    if pg_running():
        log("Postgres already running")
    else:
        log(f"starting Postgres on localhost:{port}")
        # The server outlives this call and would inherit any of our std handles,
        # keeping a caller's pipe (`uv run dev.py db | tee ...`) open forever.
        started = subprocess.run(
            [pg("pg_ctl"), "-D", str(PGDATA), "-l", str(LOCAL / "postgres.log"), "-w",
             "-o", f"-p {port} -h localhost", "start"],
            stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
        if started.returncode != 0:
            sys.exit("Postgres failed to start; see .local/postgres.log")

    pg_env = {**os.environ, "PGPASSWORD": password}
    psql = [pg("psql"), "-h", "127.0.0.1", "-p", str(port), "-U", user, "-d", "postgres", "-tAc"]
    exists = subprocess.run([*psql, f"SELECT 1 FROM pg_database WHERE datname='{dbname}'"],
                            env=pg_env, capture_output=True, text=True, check=True).stdout.strip()
    if not exists:
        subprocess.run([*psql, f'CREATE DATABASE "{dbname}"'], env=pg_env, check=True, capture_output=True)
        log(f"created database {dbname}")


def stop_postgres() -> None:
    if PGDATA.exists() and pg_running():
        subprocess.run([pg("pg_ctl"), "-D", str(PGDATA), "-m", "fast", "stop"], stdout=subprocess.DEVNULL)
        log("Postgres stopped")


def port_in_use(port: int) -> bool:
    with socket.socket() as s:
        s.settimeout(0.3)
        return s.connect_ex(("127.0.0.1", port)) == 0


def free_port(preferred: int) -> int:
    """Windows lets two servers bind the same port, so check before uvicorn does."""
    port = preferred
    while port_in_use(port):
        port += 1
    if port != preferred:
        log(f"port {preferred} is taken by another program; API will use {port}")
    return port


def child_env(env: dict[str, str], api_port: int) -> dict[str, str]:
    out = {**os.environ, **env}
    # Let the backend's own `uv run` pick backend/.venv instead of this script's env.
    out.pop("VIRTUAL_ENV", None)
    out["PATH"] = str(NODE_BIN) + os.pathsep + out.get("PATH", "")
    # .env paths are relative to the repo root; the API runs from backend/.
    for key, default in (("AUDIO_DROP_DIR", "data/incoming"), ("AUDIO_STORAGE_DIR", "data/audio")):
        path = (ROOT / env.get(key, default)).resolve()
        path.mkdir(parents=True, exist_ok=True)
        out[key] = str(path)
    out["VITE_API_BASE_URL"] = f"http://localhost:{api_port}"
    return out


def kill_tree(proc: subprocess.Popen) -> None:
    if proc.poll() is not None:
        return
    if os.name == "nt":
        subprocess.run(["taskkill", "/T", "/F", "/PID", str(proc.pid)], capture_output=True)
    else:
        proc.send_signal(signal.SIGINT)
        try:
            proc.wait(10)
        except subprocess.TimeoutExpired:
            proc.kill()


def run_stack(env: dict[str, str]) -> None:
    if port_in_use(5173):
        sys.exit("port 5173 is in use (the API only allows that origin via CORS); free it and retry")
    api_port = free_port(8000)
    cenv = child_env(env, api_port)
    uv = shutil.which("uv") or "uv"
    npm = shutil.which("npm", path=str(NODE_BIN)) or "npm"

    log("syncing backend Python environment (backend/.venv)")
    subprocess.run([uv, "sync", "--extra", "dev"], cwd=BACKEND, env=cenv, check=True)
    log("applying migrations and seeding admin")
    subprocess.run([uv, "run", "alembic", "upgrade", "head"], cwd=BACKEND, env=cenv, check=True)
    subprocess.run([uv, "run", "python", "-m", "app.seed"], cwd=BACKEND, env=cenv, check=True)

    if not (FRONTEND / "node_modules").exists():
        log("installing frontend packages (frontend/node_modules)")
        subprocess.run([npm, "ci", "--no-audit", "--no-fund"], cwd=FRONTEND, env=cenv, check=True)

    procs = [
        subprocess.Popen([uv, "run", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", str(api_port), "--reload"],
                         cwd=BACKEND, env=cenv),
        subprocess.Popen([npm, "run", "dev", "--", "--host", "127.0.0.1"], cwd=FRONTEND, env=cenv),
    ]
    log(f"API  -> http://localhost:{api_port}/docs")
    log(f"Web  -> http://localhost:5173  (login {env.get('ADMIN_EMAIL')})")
    log("Ctrl+C to stop everything")
    try:
        while all(p.poll() is None for p in procs):
            time.sleep(0.5)
        log("a process exited; shutting down")
    except KeyboardInterrupt:
        pass
    finally:
        for p in procs:
            kill_tree(p)


def main() -> None:
    cmd = sys.argv[1] if len(sys.argv) > 1 else "up"
    if cmd == "stop":
        stop_postgres()
        return
    env = ensure_env()
    start_postgres(env)
    if cmd == "db":
        log("Postgres is running; stop it with `uv run dev.py stop`")
        return
    try:
        run_stack(env)
    finally:
        stop_postgres()


if __name__ == "__main__":
    main()
