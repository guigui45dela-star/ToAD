import json
import logging
import os
import re
import secrets
import shutil
import sqlite3
import subprocess
import threading
import time
import uuid
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from contextlib import asynccontextmanager, contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

import bcrypt
import requests
from fastapi import Depends, FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, JSONResponse, Response
import jwt
from pydantic import BaseModel, Field
from starlette.responses import RedirectResponse

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("toad")

ROOT = Path("/data")
STATIC_DIR = Path("/src")
AD_MINER_DIR = Path("/ad_miner_src")
BH_STATUS_FILE = ROOT / "_bloodhound_current.json"
SETUP_FLAG = ROOT / "config" / "installed.flag"

BLOODHOUND_HOST_DIR = "/root/.config/bloodhound"
BLOODHOUND_PROJECT_NAME = "bloodhound"

BLOODHOUND_URL = os.getenv("BLOODHOUND_URL")
BLOODHOUND_USERNAME = os.getenv("BLOODHOUND_USERNAME")
BLOODHOUND_PASSWORD = os.getenv("BLOODHOUND_PASSWORD")

NEO4J_URL = os.getenv("NEO4J_URL")
NEO4J_USER = os.getenv("NEO4J_USER")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD")

INGEST_WAIT_SECONDS = int(os.getenv("INGEST_WAIT_SECONDS", "30"))
BLOODHOUND_MODE = os.getenv("BLOODHOUND_MODE", "local")
API_TOKEN = os.getenv("API_TOKEN", "")

JWT_SECRET = os.getenv("JWT_SECRET", "")
JWT_ALGORITHM = "HS256"
JWT_EXPIRATION_HOURS = int(os.getenv("JWT_EXPIRATION_HOURS", "24"))
ADMIN_DEFAULT_PASSWORD = os.getenv("ADMIN_DEFAULT_PASSWORD", "")

DB_PATH = ROOT / "config" / "toad_users.db"

VALID_ROLES = {"admin", "user", "viewer"}

MAX_PINGCASTLE_SIZE = 50 * 1024 * 1024
MAX_SHARPHOUND_SIZE = 500 * 1024 * 1024

RATE_LIMIT_MAX = 120
RATE_LIMIT_WINDOW = 60

@asynccontextmanager
async def lifespan(app: FastAPI):
    global JWT_SECRET
    if not JWT_SECRET and not API_TOKEN:
        JWT_SECRET = secrets.token_hex(32)
        logger.critical("Aucune auth configuree (JWT_SECRET/API_TOKEN). JWT_SECRET ephemere genere.")
        logger.critical("Les tokens ne survivront pas a un redemarrage. Configurez JWT_SECRET dans .env")
    init_db()
    ensure_default_admin()
    yield


app = FastAPI(lifespan=lifespan)
_job_executor = ThreadPoolExecutor(max_workers=3, thread_name_prefix="toad-job")
_rate_limit_store: dict[str, list[float]] = defaultdict(list)


class UserCreate(BaseModel):
    username: str = Field(..., min_length=3, max_length=64)
    password: str = Field(..., min_length=8)
    role: str = Field(default="viewer")


class UserUpdate(BaseModel):
    username: Optional[str] = Field(None, min_length=3, max_length=64)
    role: Optional[str] = None
    is_active: Optional[bool] = None


class PasswordReset(BaseModel):
    new_password: str = Field(..., min_length=8)


class LoginRequest(BaseModel):
    username: str
    password: str


@contextmanager
def get_db():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db():
    with get_db() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                role TEXT NOT NULL DEFAULT 'viewer',
                created_at TEXT NOT NULL,
                is_active INTEGER NOT NULL DEFAULT 1
            )
        """)
        conn.commit()


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + (expires_delta or timedelta(hours=JWT_EXPIRATION_HOURS))
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, JWT_SECRET, algorithm=JWT_ALGORITHM)


def decode_token(token: str) -> dict:
    return jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])


def db_get_user_by_username(conn, username: str) -> Optional[dict]:
    row = conn.execute("SELECT * FROM users WHERE username = ?", (username,)).fetchone()
    return dict(row) if row else None


def db_get_user_by_id(conn, user_id: int) -> Optional[dict]:
    row = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
    return dict(row) if row else None


def db_list_users(conn) -> list[dict]:
    rows = conn.execute("SELECT id, username, role, created_at, is_active FROM users ORDER BY id").fetchall()
    return [dict(r) for r in rows]


def db_create_user(conn, username: str, password_hash: str, role: str) -> int:
    now = datetime.now(timezone.utc).isoformat()
    cur = conn.execute(
        "INSERT INTO users (username, password_hash, role, created_at, is_active) VALUES (?, ?, ?, ?, 1)",
        (username, password_hash, role, now),
    )
    return cur.lastrowid


def db_update_user(conn, user_id: int, **fields):
    allowed = {"username", "role", "is_active"}
    updates = {k: v for k, v in fields.items() if k in allowed and v is not None}
    if not updates:
        return
    if "is_active" in updates:
        updates["is_active"] = 1 if updates["is_active"] else 0
    set_clause = ", ".join(f"{k} = ?" for k in updates)
    values = list(updates.values()) + [user_id]
    conn.execute(f"UPDATE users SET {set_clause} WHERE id = ?", values)


def db_delete_user(conn, user_id: int):
    conn.execute("DELETE FROM users WHERE id = ?", (user_id,))


def db_change_password(conn, user_id: int, new_hash: str):
    conn.execute("UPDATE users SET password_hash = ? WHERE id = ?", (new_hash, user_id))


def db_count_users(conn) -> int:
    return conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]


def ensure_default_admin():
    with get_db() as conn:
        if db_count_users(conn) > 0:
            return
        username = os.getenv("ADMIN_DEFAULT_USERNAME", "admin")
        password = ADMIN_DEFAULT_PASSWORD
        if not password or password == "admin":
            password = secrets.token_urlsafe(16)
            logger.warning("=" * 60)
            logger.warning(f"Admin cree avec mot de passe aleatoire : {password}")
            logger.warning("Changez-le immediatement apres la premiere connexion !")
            logger.warning("=" * 60)
        pw_hash = hash_password(password)
        db_create_user(conn, username, pw_hash, "admin")
        logger.info(f"Default admin user created: {username}")


def get_current_user(request: Request) -> dict:
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Token manquant")
    token = auth_header[7:]

    if JWT_SECRET:
        try:
            payload = decode_token(token)
            user_id = payload.get("sub")
            if user_id is None:
                raise HTTPException(status_code=401, detail="Token invalide")
            with get_db() as conn:
                user = db_get_user_by_id(conn, int(user_id))
            if not user:
                raise HTTPException(status_code=401, detail="Utilisateur introuvable")
            if not user["is_active"]:
                raise HTTPException(status_code=401, detail="Compte désactivé")
            return user
        except jwt.InvalidTokenError:
            if API_TOKEN and token == API_TOKEN:
                with get_db() as conn:
                    admin = conn.execute("SELECT * FROM users WHERE role = 'admin' LIMIT 1").fetchone()
                    if admin:
                        return dict(admin)
                return {"id": 0, "username": "api-token", "role": "admin", "is_active": 1, "created_at": ""}
            raise HTTPException(status_code=401, detail="Token invalide ou expiré")

    if API_TOKEN and token == API_TOKEN:
        return {"id": 0, "username": "api-token", "role": "admin", "is_active": 1, "created_at": ""}

    raise HTTPException(status_code=401, detail="Non authentifié")


def require_role(*roles: str):
    def checker(user: dict = Depends(get_current_user)):
        if user["role"] not in roles:
            raise HTTPException(status_code=403, detail="Permissions insuffisantes")
        return user
    return checker


def require_auth(user: dict = Depends(get_current_user)) -> dict:
    return user


@app.middleware("http")
async def auth_middleware(request: Request, call_next):
    public_paths = ("/api/setup", "/api/health", "/api/auth/login")
    if request.url.path.startswith("/api/") and not any(request.url.path.startswith(p) for p in public_paths):
        auth_header = request.headers.get("Authorization", "")
        if not auth_header.startswith("Bearer "):
            return JSONResponse(status_code=401, content={"detail": "Unauthorized"})
        token = auth_header[7:]

        authenticated = False

        if JWT_SECRET:
            try:
                payload = decode_token(token)
                user_id = payload.get("sub")
                if user_id is not None:
                    with get_db() as conn:
                        user = db_get_user_by_id(conn, int(user_id))
                    if user and user["is_active"]:
                        request.state.user = user
                        authenticated = True
            except (jwt.InvalidTokenError, ValueError, KeyError):
                pass

        if not authenticated and API_TOKEN and token == API_TOKEN:
            request.state.user = {"id": 0, "username": "api-token", "role": "admin", "is_active": 1, "created_at": ""}
            authenticated = True

        if not authenticated:
            return JSONResponse(status_code=401, content={"detail": "Unauthorized"})

    return await call_next(request)


@app.middleware("http")
async def security_headers_middleware(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Content-Security-Policy"] = "default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'; img-src 'self' data:;"
    return response


@app.middleware("http")
async def rate_limit_middleware(request: Request, call_next):
    client_ip = request.client.host if request.client else "unknown"
    now = time.time()
    _rate_limit_store[client_ip] = [t for t in _rate_limit_store[client_ip] if now - t < RATE_LIMIT_WINDOW]
    if len(_rate_limit_store[client_ip]) >= RATE_LIMIT_MAX:
        return JSONResponse(status_code=429, content={"detail": "Trop de requêtes, veuillez réessayer plus tard."})
    _rate_limit_store[client_ip].append(now)
    return await call_next(request)


@app.middleware("http")
async def setup_redirect_middleware(request: Request, call_next):
    if not is_setup_complete() and request.method == "GET":
        path = request.url.path
        if path.startswith("/api/") or path.startswith("/setup") or path.startswith("/assets"):
            return await call_next(request)
        return RedirectResponse("/setup")
    return await call_next(request)


def is_setup_complete() -> bool:
    return SETUP_FLAG.exists()


def get_config() -> dict:
    config_file = ROOT / "config" / "toad.json"
    if config_file.exists():
        try:
            return json.loads(config_file.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {}


def save_config(config: dict):
    config_file = ROOT / "config" / "toad.json"
    config_file.parent.mkdir(parents=True, exist_ok=True)
    config_file.write_text(
        json.dumps(config, indent=2, ensure_ascii=False), encoding="utf-8"
    )


# ─── Job system ───────────────────────────────────────────────────────────────

_jobs: dict = {}
_jobs_lock = threading.Lock()


def create_job(label: str) -> str:
    job_id = str(uuid.uuid4())
    with _jobs_lock:
        _jobs[job_id] = {
            "status": "running",
            "label": label,
            "message": "Démarrage...",
            "steps": [],
            "result": None,
            "created_at": time.time(),
        }
    return job_id


def job_step(job_id: str, message: str):
    with _jobs_lock:
        if job_id in _jobs:
            _jobs[job_id]["message"] = message
            _jobs[job_id]["steps"].append(message)


def job_done(job_id: str, message: str, result=None):
    with _jobs_lock:
        if job_id in _jobs:
            _jobs[job_id]["status"] = "done"
            _jobs[job_id]["message"] = message
            _jobs[job_id]["result"] = result


def job_error(job_id: str, message: str):
    with _jobs_lock:
        if job_id in _jobs:
            _jobs[job_id]["status"] = "error"
            _jobs[job_id]["message"] = message


# ─── BloodHound status tracking ──────────────────────────────────────────────


def write_bloodhound_status(slug: str, name: str, filename: str, upload_id: str = ""):
    try:
        BH_STATUS_FILE.write_text(
            json.dumps(
                {
                    "slug": slug,
                    "name": name,
                    "file": filename,
                    "imported_at": datetime.now().strftime("%d/%m/%Y %H:%M"),
                    "upload_id": upload_id,
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
    except Exception as e:
        logger.warning(f"Failed to write BH status: {e}")


def read_bloodhound_status() -> dict:
    try:
        if BH_STATUS_FILE.exists():
            return json.loads(BH_STATUS_FILE.read_text(encoding="utf-8"))
    except Exception as e:
        logger.warning(f"Failed to read BH status: {e}")
    return {
        "slug": None,
        "name": None,
        "file": None,
        "imported_at": None,
        "upload_id": "",
    }


def clear_bloodhound_status():
    try:
        BH_STATUS_FILE.write_text(
            json.dumps(
                {
                    "slug": None,
                    "name": None,
                    "file": None,
                    "imported_at": None,
                    "reset_at": datetime.now().strftime("%d/%m/%Y %H:%M"),
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
    except Exception as e:
        logger.warning(f"Failed to clear BH status: {e}")


# ─── Helpers ──────────────────────────────────────────────────────────────────


def sanitize_slug(value: str) -> str:
    value = value.strip().lower()
    value = value.replace(" ", "-")
    value = re.sub(r"[^a-z0-9_-]", "", value)
    if not value:
        raise HTTPException(status_code=400, detail="Slug client invalide.")
    if len(value) > 64:
        raise HTTPException(status_code=400, detail="Slug trop long (max 64 caractères).")
    return value


def now_slug() -> str:
    return datetime.now().strftime("%Y%m%d_%H%M%S") + "_" + uuid.uuid4().hex[:6]


def client_display_name(client_path: Path, slug: str) -> str:
    metadata_file = client_path / "client.json"
    if metadata_file.exists():
        try:
            data = json.loads(metadata_file.read_text(encoding="utf-8"))
            name = data.get("name")
            if name:
                return name
        except Exception as e:
            logger.warning(f"Failed to read client name: {e}")
    return slug.replace("-", " ").replace("_", " ").title()


def latest_file_date(path: Path):
    if not path.exists():
        return None
    try:
        latest_time = 0
        for entry in path.iterdir():
            if entry.is_file():
                mtime = entry.stat().st_mtime
                if mtime > latest_time:
                    latest_time = mtime
        if latest_time == 0:
            return None
        return datetime.fromtimestamp(latest_time).strftime("%d/%m/%Y %H:%M")
    except OSError:
        return None


def safe_path(base: Path, requested_path: str) -> Path:
    requested = (base / requested_path).resolve()
    base_resolved = base.resolve()
    base_prefix = str(base_resolved) + "/"
    if not (str(requested).startswith(base_prefix) or requested == base_resolved):
        raise HTTPException(status_code=403, detail="Forbidden")
    return requested


def ensure_client_dirs(client_path: Path):
    (client_path / "ad-miner").mkdir(parents=True, exist_ok=True)
    (client_path / "pingcastle").mkdir(parents=True, exist_ok=True)
    (client_path / "sources" / "sharphound").mkdir(parents=True, exist_ok=True)
    (client_path / "sources" / "pingcastle").mkdir(parents=True, exist_ok=True)


def write_client_metadata(client_path: Path, name: str, slug: str, extra: dict = None):
    metadata_file = client_path / "client.json"
    if metadata_file.exists():
        try:
            metadata = json.loads(metadata_file.read_text(encoding="utf-8"))
        except Exception as e:
            logger.warning(f"Failed to read metadata: {e}")
            metadata = {}
    else:
        metadata = {}
    metadata["name"] = name
    metadata["slug"] = slug
    if "created_at" not in metadata:
        metadata["created_at"] = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
    metadata["updated_at"] = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
    if extra:
        metadata.update(extra)
    metadata_file.write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def read_client_metadata(client_path: Path) -> dict:
    metadata_file = client_path / "client.json"
    if metadata_file.exists():
        try:
            return json.loads(metadata_file.read_text(encoding="utf-8"))
        except Exception as e:
            logger.warning(f"Failed to read client metadata: {e}")
    return {}


def log_event(slug: str, event: str):
    try:
        if slug == "_system":
            log_file = ROOT / "events.log"
        else:
            client_path = ROOT / slug
            if not client_path.exists():
                return
            log_file = client_path / "events.log"
        ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with open(log_file, "a", encoding="utf-8") as f:
            f.write(f"[{ts}] {event}\n")
    except Exception as e:
        logger.warning(f"Failed to log event: {e}")


def count_sharphound_zips(client_path: Path) -> int:
    sh_dir = client_path / "sources" / "sharphound"
    if not sh_dir.exists():
        return 0
    return sum(1 for f in sh_dir.iterdir() if f.suffix.lower() == ".zip")


def _validate_html_content(content: bytes) -> bool:
    text_start = content[:1024].decode("utf-8", errors="ignore").strip().lower()
    return text_start.startswith(("<!", "<html", "<head", "<body", "<div", "<p", "<span", "<table", "<script"))


def _validate_zip_magic(content: bytes) -> bool:
    return content[:4] == b"PK\x03\x04" or content[:4] == b"PK\x05\x06"


# ─── Docker / BloodHound ──────────────────────────────────────────────────────


def run_bloodhound_compose(args):
    command = [
        "docker",
        "run",
        "--rm",
        "-v",
        "/var/run/docker.sock:/var/run/docker.sock",
        "-v",
        f"{BLOODHOUND_HOST_DIR}:{BLOODHOUND_HOST_DIR}",
        "-w",
        BLOODHOUND_HOST_DIR,
        "docker:27-cli",
        "docker",
        "compose",
        "-p",
        BLOODHOUND_PROJECT_NAME,
    ] + args
    return subprocess.run(command, capture_output=True, text=True, timeout=300)


def bloodhound_login() -> str:
    payload = {
        "login_method": "secret",
        "username": BLOODHOUND_USERNAME,
        "secret": BLOODHOUND_PASSWORD,
    }
    try:
        response = requests.post(
            f"{BLOODHOUND_URL}/api/v2/login", json=payload, timeout=60
        )
    except Exception as e:
        logger.error(f"BloodHound connection failed: {e}")
        raise HTTPException(
            status_code=500, detail="Impossible de contacter BloodHound"
        )
    if response.status_code >= 400:
        logger.error(f"BloodHound auth failed: {response.status_code} - {response.text}")
        raise HTTPException(
            status_code=500,
            detail="Authentification BloodHound échouée",
        )
    data = response.json()
    try:
        return data["data"]["session_token"]
    except Exception as e:
        logger.error(f"Unexpected BloodHound login response: {data}")
        raise HTTPException(
            status_code=500, detail="Erreur de connexion BloodHound"
        )


def upload_sharphound_to_bloodhound(zip_path: Path) -> dict:
    token = bloodhound_login()
    headers = {
        "Accept": "application/json, text/plain, */*",
        "Authorization": f"Bearer {token}",
    }

    start = requests.post(
        f"{BLOODHOUND_URL}/api/v2/file-upload/start", headers=headers, timeout=60
    )
    if start.status_code >= 400:
        logger.error(f"BloodHound upload start failed: {start.text}")
        raise HTTPException(
            status_code=500,
            detail="Impossible de créer le job BloodHound",
        )
    try:
        upload_id = start.json()["data"]["id"]
    except Exception as e:
        logger.error(f"Unexpected upload start response: {start.text}")
        raise HTTPException(
            status_code=500, detail="Erreur lors de l'upload SharpHound"
        )

    upload_headers = {
        "accept": "*/*",
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/zip",
    }
    with zip_path.open("rb") as f:
        upload = requests.post(
            f"{BLOODHOUND_URL}/api/v2/file-upload/{upload_id}",
            headers=upload_headers,
            data=f.read(),
            timeout=600,
        )
    if upload.status_code >= 400:
        logger.error(f"SharpHound upload failed: {upload.text}")
        raise HTTPException(
            status_code=500, detail="Upload ZIP échoué"
        )

    end = requests.post(
        f"{BLOODHOUND_URL}/api/v2/file-upload/{upload_id}/end",
        headers=headers,
        timeout=120,
    )
    if end.status_code >= 400:
        logger.error(f"BloodHound upload end failed: {end.text}")
        raise HTTPException(
            status_code=500, detail="Erreur lors de la finalisation de l'upload"
        )

    return {"upload_id": upload_id, "message": "ZIP SharpHound envoyé à BloodHound."}


def wait_for_bloodhound_ingestion(job_id: str = None, max_wait: int = 600) -> bool:
    """
    Interroge l'API BloodHound toutes les 8s jusqu'à ce qu'il n'y ait plus
    de jobs actifs (ingestion terminée) ou que max_wait soit atteint.
    Retourne True si l'ingestion est confirmée terminée, False si timeout.
    """
    try:
        token = bloodhound_login()
    except Exception:
        return False

    headers = {"Authorization": f"Bearer {token}"}
    start = time.time()
    ACTIVE_STATES = {
        "running",
        "analyzing",
        "ingesting",
        "queued",
        "processing",
        "scheduled",
    }

    time.sleep(5)  # délai minimal avant le premier poll

    while True:
        elapsed = int(time.time() - start)

        if elapsed >= max_wait:
            if job_id:
                job_step(
                    job_id,
                    f"Timeout attente ingestion BloodHound ({max_wait}s) — génération lancée quand même.",
                )
            return False

        try:
            r = requests.get(
                f"{BLOODHOUND_URL}/api/v2/jobs", headers=headers, timeout=15
            )

            if r.ok:
                raw = r.json().get("data", [])
                if isinstance(raw, list):
                    jobs = raw
                elif isinstance(raw, dict):
                    jobs = raw.get("jobs") or raw.get("data") or []
                else:
                    jobs = []

                active = [
                    j
                    for j in jobs
                    if str(j.get("status", "")).lower() in ACTIVE_STATES
                    or j.get("status") in (1, 2, 3)
                ]

                if job_id:
                    job_step(
                        job_id,
                        f"Attente ingestion BloodHound ({elapsed}s, {len(active)} job(s) actif(s))...",
                    )

                if not active:
                    return True

            else:
                # Endpoint indisponible : fallback sur délai fixe minimal
                if elapsed >= min(INGEST_WAIT_SECONDS * 3, 120):
                    return True
                if job_id:
                    job_step(job_id, f"Attente ingestion BloodHound ({elapsed}s)...")

        except Exception:
            if elapsed >= min(INGEST_WAIT_SECONDS * 3, 120):
                return True
            if job_id:
                job_step(job_id, f"Attente ingestion BloodHound ({elapsed}s)...")

        time.sleep(8)


def generate_ad_miner_for_client(clean_slug: str) -> dict:
    client_path = ROOT / clean_slug
    if not client_path.exists():
        raise HTTPException(status_code=404, detail="Client introuvable.")

    render_dir = AD_MINER_DIR / f"render_{clean_slug}"
    if render_dir.exists():
        logger.info(f"Nettoyage du dossier render existant: {render_dir}")
        shutil.rmtree(render_dir)

    command = [
        "python",
        "-m",
        "ad_miner",
        "-cf",
        clean_slug,
        "-b",
        NEO4J_URL,
        "-u",
        NEO4J_USER,
        "-p",
        NEO4J_PASSWORD,
    ]
    logger.info(f"Lancement AD-Miner pour {clean_slug}")
    result = subprocess.run(
        command, cwd=str(AD_MINER_DIR), capture_output=True, text=True, timeout=900
    )

    # Rapport présent → succès même si returncode != 0 (warnings Neo4j traités en erreur par AD-Miner)
    report_generated = render_dir.exists() and any(render_dir.rglob("*.html"))

    if result.returncode != 0 and not report_generated:
        logger.error(f"AD-Miner failed for {clean_slug}: {result.stderr or result.stdout}")
        raise HTTPException(
            status_code=500,
            detail="Erreur lors de la génération AD-Miner",
        )

    if not render_dir.exists():
        logger.error(f"AD-Miner terminé mais le dossier render n'existe pas: {render_dir}")
        raise HTTPException(
            status_code=500, detail="AD-Miner terminé mais rapport introuvable."
        )

    # Vérifier que le rapport contient bien des fichiers
    html_files = list(render_dir.rglob("*.html"))
    if not html_files:
        logger.error(f"AD-Miner a généré un dossier mais aucun fichier HTML: {render_dir}")
        raise HTTPException(
            status_code=500, detail="AD-Miner n'a généré aucun rapport HTML."
        )
    
    logger.info(f"AD-Miner a généré {len(html_files)} fichiers HTML dans {render_dir}")

    target_dir = client_path / "ad-miner"
    # Copy to a temp dir first, then atomically swap — évite les ENOTEMPTY
    # si l'ancien dossier est verrouillé ou partiellement supprimé.
    tmp_dir = target_dir.parent / f".ad-miner-tmp-{clean_slug}"
    if tmp_dir.exists():
        shutil.rmtree(tmp_dir)
    
    logger.info(f"Copie du rapport de {render_dir} vers {tmp_dir}")
    shutil.copytree(render_dir, tmp_dir)
    
    if target_dir.exists():
        logger.info(f"Suppression de l'ancien rapport: {target_dir}")
        shutil.rmtree(target_dir)
    
    logger.info(f"Renommage de {tmp_dir} vers {target_dir}")
    tmp_dir.rename(target_dir)
    
    logger.info(f"Rapport AD-Miner copié avec succès vers {target_dir}")

    warning = ""
    if result.returncode != 0:
        warning = " (avec avertissements Neo4j)"

    return {
        "status": "ok",
        "message": f"Rapport AD-Miner généré{warning}.",
        "url": f"/{clean_slug}/ad-miner/",
    }


# ─── Background tasks ─────────────────────────────────────────────────────────


def _full_audit_background(
    job_id: str, clean_name: str, clean_slug: str, pc_bytes: bytes, sh_bytes: bytes
):
    try:
        client_path = ROOT / clean_slug

        job_step(job_id, "Création des répertoires client...")
        ensure_client_dirs(client_path)
        write_client_metadata(client_path, clean_name, clean_slug)
        log_event(clean_slug, f"client_created name={clean_name}")

        job_step(job_id, "Archivage des fichiers sources...")
        ts = now_slug()
        pc_src = client_path / "sources" / "pingcastle" / f"pingcastle_{ts}.html"
        pc_dst = client_path / "pingcastle" / "index.html"
        sh_src = client_path / "sources" / "sharphound" / f"sharphound_{ts}.zip"
        pc_src.write_bytes(pc_bytes)
        pc_dst.write_bytes(pc_bytes)
        sh_src.write_bytes(sh_bytes)
        log_event(clean_slug, f"pingcastle_uploaded file={pc_src.name}")
        log_event(clean_slug, f"sharphound_uploaded file={sh_src.name}")

        job_step(job_id, "Envoi du ZIP vers BloodHound...")
        upload_result = upload_sharphound_to_bloodhound(sh_src)
        write_bloodhound_status(
            clean_slug, clean_name, sh_src.name, upload_result.get("upload_id", "")
        )
        log_event(
            clean_slug,
            f"bloodhound_ingest_started upload_id={upload_result.get('upload_id')}",
        )

        job_step(job_id, "Attente de la fin de l'ingestion BloodHound...")
        wait_for_bloodhound_ingestion(job_id=job_id, max_wait=600)
        log_event(clean_slug, "bloodhound_ingest_finished")

        job_step(
            job_id, "Génération AD-Miner en cours (peut prendre plusieurs minutes)..."
        )
        generate_ad_miner_for_client(clean_slug)
        log_event(clean_slug, "ad_miner_generated")

        # Mise à jour de la date du dernier audit complet
        write_client_metadata(
            client_path,
            clean_name,
            clean_slug,
            extra={"last_audit_at": datetime.now().strftime("%d/%m/%Y %H:%M")},
        )

        job_done(
            job_id,
            f"Audit complet terminé pour {clean_name}.",
            {
                "slug": clean_slug,
                "pingcastle_url": f"/{clean_slug}/pingcastle/",
                "ad_miner_url": f"/{clean_slug}/ad-miner/",
            },
        )

    except HTTPException as e:
        job_error(job_id, e.detail)
        log_event(clean_slug, f"error {e.detail}")
    except subprocess.TimeoutExpired:
        job_error(job_id, "Timeout lors de la génération AD-Miner.")
        log_event(clean_slug, "error timeout_ad_miner")
    except Exception as e:
        job_error(job_id, str(e))
        log_event(clean_slug, f"error {e}")


def _ad_miner_background(job_id: str, clean_slug: str):
    try:
        # Attendre que BloodHound finisse l'ingestion avant de lancer AD-Miner
        job_step(job_id, "Attente de la fin de l'ingestion BloodHound...")
        wait_for_bloodhound_ingestion(job_id=job_id, max_wait=600)
        log_event(clean_slug, "bloodhound_ingest_finished_before_ad_miner")
        
        job_step(job_id, f"Génération AD-Miner pour {clean_slug}...")
        result = generate_ad_miner_for_client(clean_slug)
        log_event(clean_slug, "ad_miner_generated")
        job_done(job_id, "Rapport AD-Miner généré.", result)
    except HTTPException as e:
        job_error(job_id, e.detail)
    except subprocess.TimeoutExpired:
        job_error(job_id, "Timeout lors de la génération AD-Miner.")
    except Exception as e:
        job_error(job_id, str(e))


# ─── Auth endpoints ───────────────────────────────────────────────────────────


@app.post("/api/auth/login")
def auth_login(body: LoginRequest):
    if not JWT_SECRET:
        raise HTTPException(status_code=503, detail="Authentification JWT non configurée")
    with get_db() as conn:
        user = db_get_user_by_username(conn, body.username)
    if not user:
        raise HTTPException(status_code=401, detail="Identifiants invalides")
    if not verify_password(body.password, user["password_hash"]):
        raise HTTPException(status_code=401, detail="Identifiants invalides")
    if not user["is_active"]:
        raise HTTPException(status_code=401, detail="Compte désactivé")
    token = create_access_token({"sub": str(user["id"]), "username": user["username"], "role": user["role"]})
    return {
        "access_token": token,
        "token_type": "bearer",
        "user": {
            "id": user["id"],
            "username": user["username"],
            "role": user["role"],
        },
    }


@app.post("/api/auth/logout")
def auth_logout():
    return {"status": "ok", "message": "Déconnexion réussie"}


@app.get("/api/auth/me")
def auth_me(user: dict = Depends(get_current_user)):
    return {
        "id": user["id"],
        "username": user["username"],
        "role": user["role"],
        "is_active": user["is_active"],
        "created_at": user.get("created_at"),
    }


# ─── User management endpoints (admin only) ──────────────────────────────────


@app.get("/api/users")
def list_users(admin: dict = Depends(require_role("admin"))):
    with get_db() as conn:
        return db_list_users(conn)


@app.post("/api/users")
def create_user(body: UserCreate, admin: dict = Depends(require_role("admin"))):
    if body.role not in VALID_ROLES:
        raise HTTPException(status_code=400, detail=f"Rôle invalide. Valeurs acceptées: {', '.join(sorted(VALID_ROLES))}")
    with get_db() as conn:
        existing = db_get_user_by_username(conn, body.username)
        if existing:
            raise HTTPException(status_code=409, detail="Nom d'utilisateur déjà pris")
        pw_hash = hash_password(body.password)
        user_id = db_create_user(conn, body.username, pw_hash, body.role)
    return {"status": "ok", "id": user_id, "message": f"Utilisateur « {body.username} » créé."}


@app.put("/api/users/{user_id}")
def update_user(user_id: int, body: UserUpdate, admin: dict = Depends(require_role("admin"))):
    if body.role and body.role not in VALID_ROLES:
        raise HTTPException(status_code=400, detail=f"Rôle invalide. Valeurs acceptées: {', '.join(sorted(VALID_ROLES))}")
    with get_db() as conn:
        user = db_get_user_by_id(conn, user_id)
        if not user:
            raise HTTPException(status_code=404, detail="Utilisateur introuvable")
        if body.username:
            dup = db_get_user_by_username(conn, body.username)
            if dup and dup["id"] != user_id:
                raise HTTPException(status_code=409, detail="Nom d'utilisateur déjà pris")
        db_update_user(conn, user_id, username=body.username, role=body.role, is_active=body.is_active)
    return {"status": "ok", "message": "Utilisateur mis à jour."}


@app.delete("/api/users/{user_id}")
def delete_user(user_id: int, admin: dict = Depends(require_role("admin"))):
    with get_db() as conn:
        user = db_get_user_by_id(conn, user_id)
        if not user:
            raise HTTPException(status_code=404, detail="Utilisateur introuvable")
        if user["id"] == admin.get("id"):
            raise HTTPException(status_code=400, detail="Impossible de supprimer votre propre compte")
        db_delete_user(conn, user_id)
    return {"status": "ok", "message": f"Utilisateur « {user['username']} » supprimé."}


@app.post("/api/users/{user_id}/reset-password")
def reset_password(user_id: int, body: PasswordReset, admin: dict = Depends(require_role("admin"))):
    with get_db() as conn:
        user = db_get_user_by_id(conn, user_id)
        if not user:
            raise HTTPException(status_code=404, detail="Utilisateur introuvable")
        new_hash = hash_password(body.new_password)
        db_change_password(conn, user_id, new_hash)
    return {"status": "ok", "message": "Mot de passe réinitialisé."}


# ─── API routes ───────────────────────────────────────────────────────────────


@app.get("/api/audits")
def audits(user: dict = Depends(require_role("admin", "user", "viewer"))):
    result = []
    if not ROOT.exists():
        return result
    bh_active_slug = read_bloodhound_status().get("slug")
    for client_path in sorted(ROOT.iterdir()):
        if not client_path.is_dir():
            continue
        slug = client_path.name
        if slug.startswith("_") or slug == "config":
            continue
        ad_miner_index = client_path / "ad-miner" / "index.html"
        pingcastle_index = client_path / "pingcastle" / "index.html"
        metadata = read_client_metadata(client_path)
        result.append(
            {
                "slug": slug,
                "name": metadata.get("name")
                or slug.replace("-", " ").replace("_", " ").title(),
                "created_at": metadata.get("created_at"),
                "last_audit_at": metadata.get("last_audit_at"),
                "ad_miner": {
                    "available": ad_miner_index.exists(),
                    "url": f"/{slug}/ad-miner/",
                    "date": latest_file_date(client_path / "ad-miner"),
                },
                "pingcastle": {
                    "available": pingcastle_index.exists(),
                    "url": f"/{slug}/pingcastle/",
                    "date": latest_file_date(client_path / "pingcastle"),
                },
                "sources": {
                    "sharphound_date": latest_file_date(
                        client_path / "sources" / "sharphound"
                    ),
                    "sharphound_count": count_sharphound_zips(client_path),
                    "pingcastle_date": latest_file_date(
                        client_path / "sources" / "pingcastle"
                    ),
                },
                "bloodhound_active": bh_active_slug == slug,
            }
        )
    return result


@app.get("/api/bloodhound/status")
def get_bloodhound_status(user: dict = Depends(require_role("admin", "user", "viewer"))):
    return read_bloodhound_status()


@app.get("/api/health")
def health_check():
    return {"status": "ok", "timestamp": datetime.now().isoformat(), "version": "1.2.0"}


@app.get("/api/jobs/{job_id}")
def get_job(job_id: str, user: dict = Depends(require_role("admin", "user", "viewer"))):
    now = time.time()
    with _jobs_lock:
        expired = [jid for jid, j in _jobs.items() if now - j.get("created_at", 0) > 3600]
        for jid in expired:
            del _jobs[jid]
        if job_id not in _jobs:
            raise HTTPException(status_code=404, detail="Job introuvable.")
        return dict(_jobs[job_id])


@app.post("/api/clients")
def create_client(name: str = Form(...), slug: str = Form(...), user: dict = Depends(require_role("admin", "user"))):
    clean_slug = sanitize_slug(slug)
    clean_name = name.strip()
    if not clean_name:
        raise HTTPException(status_code=400, detail="Nom client invalide.")
    client_path = ROOT / clean_slug
    if client_path.exists():
        raise HTTPException(status_code=409, detail="Ce client existe déjà.")
    ensure_client_dirs(client_path)
    write_client_metadata(client_path, clean_name, clean_slug)
    log_event(clean_slug, f"client_created name={clean_name}")
    return {
        "status": "ok",
        "message": f"Client « {clean_name} » créé.",
        "slug": clean_slug,
    }


@app.delete("/api/clients/{slug}")
def delete_client(slug: str, user: dict = Depends(require_role("admin", "user"))):
    clean_slug = sanitize_slug(slug)
    client_path = ROOT / clean_slug
    if not client_path.exists():
        raise HTTPException(status_code=404, detail="Client introuvable.")
    name = client_display_name(client_path, clean_slug)
    shutil.rmtree(client_path)
    log_event("_system", f"client_deleted slug={clean_slug} name={name}")
    bh = read_bloodhound_status()
    if bh.get("slug") == clean_slug:
        clear_bloodhound_status()
    return {"status": "ok", "message": f"Client « {name} » supprimé."}


@app.post("/api/clients/{slug}/pingcastle")
async def upload_pingcastle(slug: str, report: UploadFile = File(...), user: dict = Depends(require_role("admin", "user"))):
    clean_slug = sanitize_slug(slug)
    client_path = ROOT / clean_slug
    if not client_path.exists():
        raise HTTPException(status_code=404, detail="Client introuvable.")
    filename = report.filename or ""
    if not filename.lower().endswith((".html", ".htm")):
        raise HTTPException(
            status_code=400, detail="Le rapport PingCastle doit être un fichier HTML."
        )
    ensure_client_dirs(client_path)
    ts = now_slug()
    source_file = client_path / "sources" / "pingcastle" / f"pingcastle_{ts}.html"
    target_file = client_path / "pingcastle" / "index.html"
    content = await report.read()
    if len(content) > MAX_PINGCASTLE_SIZE:
        raise HTTPException(
            status_code=413, detail="Fichier trop volumineux (max 50 Mo)."
        )
    if not _validate_html_content(content):
        raise HTTPException(
            status_code=400, detail="Le fichier ne semble pas être un rapport HTML valide."
        )
    source_file.write_bytes(content)
    target_file.write_bytes(content)
    log_event(clean_slug, f"pingcastle_uploaded file={source_file.name}")
    return {
        "status": "ok",
        "message": "Rapport PingCastle importé.",
        "url": f"/{clean_slug}/pingcastle/",
    }


def cleanup_old_sharphound_files(client_path: Path):
    """Supprime tous les anciens fichiers SharpHound pour éviter les conflits"""
    sh_dir = client_path / "sources" / "sharphound"
    if not sh_dir.exists():
        return
    
    zip_files = list(sh_dir.glob("*.zip"))
    for old_file in zip_files:
        try:
            old_file.unlink()
            logger.info(f"Supprimé ancien fichier SharpHound: {old_file.name}")
            log_event(client_path.name, f"sharphound_cleanup file={old_file.name}")
        except Exception as e:
            logger.warning(f"Impossible de supprimer {old_file.name}: {e}")


@app.post("/api/clients/{slug}/sharphound")
async def upload_sharphound_only(slug: str, zip_file: UploadFile = File(...), user: dict = Depends(require_role("admin", "user"))):
    clean_slug = sanitize_slug(slug)
    client_path = ROOT / clean_slug
    if not client_path.exists():
        raise HTTPException(status_code=404, detail="Client introuvable.")
    filename = zip_file.filename or ""
    if not filename.lower().endswith(".zip"):
        raise HTTPException(
            status_code=400, detail="Le fichier SharpHound doit être une archive ZIP."
        )
    ensure_client_dirs(client_path)
    
    # Nettoyer les anciens fichiers SharpHound avant d'en importer un nouveau
    cleanup_old_sharphound_files(client_path)
    
    ts = now_slug()
    source_file = client_path / "sources" / "sharphound" / f"sharphound_{ts}.zip"
    content = await zip_file.read()
    if len(content) > MAX_SHARPHOUND_SIZE:
        raise HTTPException(
            status_code=413, detail="Fichier trop volumineux (max 500 Mo)."
        )
    if not _validate_zip_magic(content):
        raise HTTPException(
            status_code=400, detail="Le fichier ne semble pas être une archive ZIP valide."
        )
    source_file.write_bytes(content)
    log_event(clean_slug, f"sharphound_uploaded file={source_file.name}")
    upload_result = upload_sharphound_to_bloodhound(source_file)
    name = client_display_name(client_path, clean_slug)
    write_bloodhound_status(
        clean_slug, name, source_file.name, upload_result.get("upload_id", "")
    )
    log_event(
        clean_slug,
        f"bloodhound_ingest_started upload_id={upload_result.get('upload_id')}",
    )
    
    # Attendre que BloodHound finisse l'ingestion avant de retourner
    job_step(None, "Attente de la fin de l'ingestion BloodHound...")
    wait_for_bloodhound_ingestion(job_id=None, max_wait=600)
    log_event(clean_slug, "bloodhound_ingest_finished")
    
    return {
        "status": "ok",
        "message": "ZIP SharpHound importé dans BloodHound et ingestion terminée.",
        "bloodhound": upload_result,
    }


@app.get("/api/clients/{slug}/sharphound/files")
def list_sharphound_files(slug: str, user: dict = Depends(require_role("admin", "user", "viewer"))):
    clean_slug = sanitize_slug(slug)
    client_path = ROOT / clean_slug
    if not client_path.exists():
        raise HTTPException(status_code=404, detail="Client introuvable.")
    sh_dir = client_path / "sources" / "sharphound"
    if not sh_dir.exists():
        return []
    files = sorted(
        [f for f in sh_dir.iterdir() if f.suffix.lower() == ".zip"],
        key=lambda f: f.stat().st_mtime,
        reverse=True,
    )
    return [
        {
            "filename": f.name,
            "size": f.stat().st_size,
            "date": datetime.fromtimestamp(f.stat().st_mtime).strftime(
                "%d/%m/%Y %H:%M"
            ),
        }
        for f in files
    ]


@app.get("/api/clients/{slug}/sharphound/download/{filename}")
def download_sharphound(slug: str, filename: str, user: dict = Depends(require_role("admin", "user", "viewer"))):
    clean_slug = sanitize_slug(slug)
    if (
        not filename.lower().endswith(".zip")
        or "/" in filename
        or "\\" in filename
        or ".." in filename
    ):
        raise HTTPException(status_code=400, detail="Nom de fichier invalide.")
    file_path = ROOT / clean_slug / "sources" / "sharphound" / filename
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="Fichier introuvable.")
    return FileResponse(
        path=str(file_path), filename=filename, media_type="application/zip"
    )


@app.post("/api/clients/{slug}/ad-miner/generate")
def generate_ad_miner(slug: str, user: dict = Depends(require_role("admin", "user"))):
    clean_slug = sanitize_slug(slug)
    client_path = ROOT / clean_slug
    if not client_path.exists():
        raise HTTPException(status_code=404, detail="Client introuvable.")
    job_id = create_job(f"AD-Miner — {clean_slug}")
    _job_executor.submit(_ad_miner_background, job_id, clean_slug)
    return {"job_id": job_id, "status": "running"}


@app.post("/api/audits/full")
async def create_full_audit(
    name: str = Form(...),
    slug: str = Form(...),
    pingcastle_report: UploadFile = File(...),
    sharphound_zip: UploadFile = File(...),
    user: dict = Depends(require_role("admin", "user")),
):
    clean_slug = sanitize_slug(slug)
    clean_name = name.strip()
    if not clean_name:
        raise HTTPException(status_code=400, detail="Nom client invalide.")
    pc_name = pingcastle_report.filename or ""
    sh_name = sharphound_zip.filename or ""
    if not pc_name.lower().endswith((".html", ".htm")):
        raise HTTPException(
            status_code=400, detail="Le rapport PingCastle doit être un fichier HTML."
        )
    if not sh_name.lower().endswith(".zip"):
        raise HTTPException(
            status_code=400, detail="Le fichier SharpHound doit être une archive ZIP."
        )

    pc_bytes = await pingcastle_report.read()
    sh_bytes = await sharphound_zip.read()

    if len(pc_bytes) > MAX_PINGCASTLE_SIZE:
        raise HTTPException(
            status_code=413, detail="Fichier trop volumineux (max 50 Mo)."
        )
    if len(sh_bytes) > MAX_SHARPHOUND_SIZE:
        raise HTTPException(
            status_code=413, detail="Fichier trop volumineux (max 500 Mo)."
        )

    job_id = create_job(f"Audit complet — {clean_name}")
    _job_executor.submit(_full_audit_background, job_id, clean_name, clean_slug, pc_bytes, sh_bytes)
    return {
        "job_id": job_id,
        "status": "running",
        "message": f"Audit lancé pour {clean_name}.",
    }


@app.post("/api/bloodhound/reset")
def reset_bloodhound(user: dict = Depends(require_role("admin"))):
    try:
        log_event("_system", "bloodhound_reset_started")
        down = run_bloodhound_compose(["down", "-v"])
        if down.returncode != 0:
            logger.error(f"Docker compose down failed: {down.stderr}")
            raise HTTPException(
                status_code=500, detail="Erreur lors de la réinitialisation BloodHound"
            )
        up = run_bloodhound_compose(["up", "-d"])
        if up.returncode != 0:
            logger.error(f"Docker compose up failed: {up.stderr}")
            raise HTTPException(
                status_code=500, detail="Erreur lors du redémarrage BloodHound"
            )
        clear_bloodhound_status()
        log_event("_system", "bloodhound_reset_done")
        return {"status": "ok", "message": "BloodHound a été vidé et redémarré."}
    except subprocess.TimeoutExpired:
        raise HTTPException(
            status_code=500, detail="Timeout pendant la réinitialisation BloodHound."
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/setup")
def setup_page():
    setup_html = STATIC_DIR / "setup.html"
    if not setup_html.exists():
        raise HTTPException(status_code=404, detail="Page de setup introuvable")
    return FileResponse(setup_html)


@app.get("/api/setup/status")
def setup_status():
    return {
        "installed": is_setup_complete(),
        "mode": BLOODHOUND_MODE,
        "bloodhound_url": BLOODHOUND_URL,
        "neo4j_url": NEO4J_URL,
    }


@app.post("/api/setup/test")
def test_setup_connections(data: dict):
    results = {"bloodhound": False, "neo4j": False, "errors": []}

    bh_url = data.get("bloodhound_url", "")
    bh_user = data.get("bloodhound_username", "")
    bh_pass = data.get("bloodhound_password", "")
    neo4j_url = data.get("neo4j_url", "")
    neo4j_user = data.get("neo4j_user", "")
    neo4j_pass = data.get("neo4j_password", "")

    if bh_url and bh_user and bh_pass:
        try:
            payload = {"login_method": "secret", "username": bh_user, "secret": bh_pass}
            r = requests.post(f"{bh_url}/api/v2/login", json=payload, timeout=10)
            if r.ok:
                results["bloodhound"] = True
            else:
                results["errors"].append(
                    f"BloodHound: Authentification échouée ({r.status_code})"
                )
        except Exception as e:
            results["errors"].append(f"BloodHound: {str(e)}")

    if neo4j_url and neo4j_user and neo4j_pass:
        try:
            from neo4j import GraphDatabase

            driver = GraphDatabase.driver(neo4j_url, auth=(neo4j_user, neo4j_pass))
            driver.verify_connectivity()
            driver.close()
            results["neo4j"] = True
        except ImportError:
            results["errors"].append("Neo4j: Module neo4j non installé (test ignoré)")
            results["neo4j"] = True
        except Exception as e:
            results["errors"].append(f"Neo4j: {str(e)}")

    return results


@app.post("/api/setup/complete")
def complete_setup(data: dict):
    if is_setup_complete():
        raise HTTPException(status_code=400, detail="ToAD est déjà configuré")

    mode = data.get("mode", "local")
    config = {
        "mode": mode,
        "bloodhound_url": data.get("bloodhound_url", ""),
        "bloodhound_username": data.get("bloodhound_username", ""),
        "bloodhound_password": data.get("bloodhound_password", ""),
        "neo4j_url": data.get("neo4j_url", ""),
        "neo4j_user": data.get("neo4j_user", ""),
        "neo4j_password": data.get("neo4j_password", ""),
        "toad_port": data.get("toad_port", "9100"),
        "ingest_wait_seconds": data.get("ingest_wait_seconds", "30"),
        "created_at": datetime.now().isoformat(),
    }

    save_config(config)
    SETUP_FLAG.parent.mkdir(parents=True, exist_ok=True)
    SETUP_FLAG.write_text(datetime.now().isoformat(), encoding="utf-8")

    return {
        "status": "ok",
        "message": "Configuration sauvegardée. Redémarrez le conteneur pour appliquer les changements.",
        "restart_required": True,
    }


@app.get("/assets/{filename}")
def serve_asset(filename: str):
    asset_path = STATIC_DIR / "assets" / filename
    if not asset_path.exists() or ".." in filename or "/" in filename:
        raise HTTPException(status_code=404)
    return FileResponse(asset_path)


@app.api_route("/", methods=["GET", "HEAD"])
def homepage(request: Request):
    index_file = STATIC_DIR / "index.html"
    if not index_file.exists():
        raise HTTPException(status_code=404, detail="index.html introuvable")
    if request.method == "HEAD":
        return Response(status_code=200)
    return FileResponse(index_file)


@app.api_route("/{full_path:path}", methods=["GET", "HEAD"])
def serve_client_files(full_path: str, request: Request):
    requested = safe_path(ROOT, full_path)
    if requested.is_dir():
        index_file = requested / "index.html"
        if index_file.exists():
            if request.method == "HEAD":
                return Response(status_code=200)
            return FileResponse(index_file)
    if requested.is_file():
        if request.method == "HEAD":
            return Response(status_code=200)
        return FileResponse(requested)
    index_file = STATIC_DIR / "index.html"
    if index_file.exists():
        if request.method == "HEAD":
            return Response(status_code=200)
        return FileResponse(index_file)
    raise HTTPException(status_code=404, detail="Not Found")
