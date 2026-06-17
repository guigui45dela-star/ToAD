from fastapi import FastAPI, HTTPException, Request, UploadFile, File, Form
from fastapi.responses import FileResponse, Response, RedirectResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pathlib import Path
from datetime import datetime
import subprocess
import shutil
import re
import json
import time
import os
import requests
import uuid
import threading

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

MAX_PINGCASTLE_SIZE = 50 * 1024 * 1024  # 50 MB
MAX_SHARPHOUND_SIZE = 500 * 1024 * 1024  # 500 MB

app = FastAPI()

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
    config_file.write_text(json.dumps(config, indent=2, ensure_ascii=False), encoding="utf-8")

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
            json.dumps({
                "slug": slug,
                "name": name,
                "file": filename,
                "imported_at": datetime.now().strftime("%d/%m/%Y %H:%M"),
                "upload_id": upload_id,
            }, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
    except Exception:
        pass


def read_bloodhound_status() -> dict:
    try:
        if BH_STATUS_FILE.exists():
            return json.loads(BH_STATUS_FILE.read_text(encoding="utf-8"))
    except Exception:
        pass
    return {"slug": None, "name": None, "file": None, "imported_at": None, "upload_id": ""}


def clear_bloodhound_status():
    try:
        BH_STATUS_FILE.write_text(
            json.dumps({
                "slug": None,
                "name": None,
                "file": None,
                "imported_at": None,
                "reset_at": datetime.now().strftime("%d/%m/%Y %H:%M"),
            }, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
    except Exception:
        pass


# ─── Helpers ──────────────────────────────────────────────────────────────────

def sanitize_slug(value: str) -> str:
    value = value.strip().lower()
    value = value.replace(" ", "-")
    value = re.sub(r"[^a-z0-9_-]", "", value)
    if not value:
        raise HTTPException(status_code=400, detail="Slug client invalide.")
    return value


def now_slug() -> str:
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def client_display_name(client_path: Path, slug: str) -> str:
    metadata_file = client_path / "client.json"
    if metadata_file.exists():
        try:
            data = json.loads(metadata_file.read_text(encoding="utf-8"))
            name = data.get("name")
            if name:
                return name
        except Exception:
            pass
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
        except Exception:
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
    metadata_file.write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")


def read_client_metadata(client_path: Path) -> dict:
    metadata_file = client_path / "client.json"
    if metadata_file.exists():
        try:
            return json.loads(metadata_file.read_text(encoding="utf-8"))
        except Exception:
            pass
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
    except Exception:
        pass


def count_sharphound_zips(client_path: Path) -> int:
    sh_dir = client_path / "sources" / "sharphound"
    if not sh_dir.exists():
        return 0
    return sum(1 for f in sh_dir.iterdir() if f.suffix.lower() == ".zip")


# ─── Docker / BloodHound ──────────────────────────────────────────────────────

def run_bloodhound_compose(args):
    command = [
        "docker", "run", "--rm",
        "-v", "/var/run/docker.sock:/var/run/docker.sock",
        "-v", f"{BLOODHOUND_HOST_DIR}:{BLOODHOUND_HOST_DIR}",
        "-w", BLOODHOUND_HOST_DIR,
        "docker:27-cli",
        "docker", "compose",
        "-p", BLOODHOUND_PROJECT_NAME,
    ] + args
    return subprocess.run(command, capture_output=True, text=True, timeout=300)


def bloodhound_login() -> str:
    payload = {"login_method": "secret", "username": BLOODHOUND_USERNAME, "secret": BLOODHOUND_PASSWORD}
    try:
        response = requests.post(f"{BLOODHOUND_URL}/api/v2/login", json=payload, timeout=60)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Impossible de contacter BloodHound : {e}")
    if response.status_code >= 400:
        raise HTTPException(status_code=500, detail=f"Authentification BloodHound refusée : {response.text}")
    data = response.json()
    try:
        return data["data"]["session_token"]
    except Exception:
        raise HTTPException(status_code=500, detail=f"Réponse login BloodHound inattendue : {data}")


def upload_sharphound_to_bloodhound(zip_path: Path) -> dict:
    token = bloodhound_login()
    headers = {"Accept": "application/json, text/plain, */*", "Authorization": f"Bearer {token}"}

    start = requests.post(f"{BLOODHOUND_URL}/api/v2/file-upload/start", headers=headers, timeout=60)
    if start.status_code >= 400:
        raise HTTPException(status_code=500, detail=f"Impossible de créer le job BloodHound : {start.text}")
    try:
        upload_id = start.json()["data"]["id"]
    except Exception:
        raise HTTPException(status_code=500, detail=f"Réponse start upload inattendue : {start.text}")

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
        raise HTTPException(status_code=500, detail=f"Upload ZIP échoué : {upload.text}")

    end = requests.post(f"{BLOODHOUND_URL}/api/v2/file-upload/{upload_id}/end", headers=headers, timeout=120)
    if end.status_code >= 400:
        raise HTTPException(status_code=500, detail=f"Fin du job BloodHound échouée : {end.text}")

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
    ACTIVE_STATES = {"running", "analyzing", "ingesting", "queued", "processing", "scheduled"}

    time.sleep(5)  # délai minimal avant le premier poll

    while True:
        elapsed = int(time.time() - start)

        if elapsed >= max_wait:
            if job_id:
                job_step(job_id, f"Timeout attente ingestion BloodHound ({max_wait}s) — génération lancée quand même.")
            return False

        try:
            r = requests.get(f"{BLOODHOUND_URL}/api/v2/jobs", headers=headers, timeout=15)

            if r.ok:
                raw = r.json().get("data", [])
                if isinstance(raw, list):
                    jobs = raw
                elif isinstance(raw, dict):
                    jobs = raw.get("jobs") or raw.get("data") or []
                else:
                    jobs = []

                active = [
                    j for j in jobs
                    if str(j.get("status", "")).lower() in ACTIVE_STATES
                    or j.get("status") in (1, 2, 3)
                ]

                if job_id:
                    job_step(job_id, f"Attente ingestion BloodHound ({elapsed}s, {len(active)} job(s) actif(s))...")

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
        shutil.rmtree(render_dir)

    command = [
        "python", "-m", "ad_miner",
        "-cf", clean_slug,
        "-b", NEO4J_URL,
        "-u", NEO4J_USER,
        "-p", NEO4J_PASSWORD,
    ]
    result = subprocess.run(command, cwd=str(AD_MINER_DIR), capture_output=True, text=True, timeout=900)

    # Rapport présent → succès même si returncode != 0 (warnings Neo4j traités en erreur par AD-Miner)
    report_generated = render_dir.exists() and any(render_dir.rglob("*.html"))

    if result.returncode != 0 and not report_generated:
        raise HTTPException(status_code=500, detail=f"Erreur AD-Miner : {result.stderr or result.stdout}")

    if not render_dir.exists():
        raise HTTPException(status_code=500, detail="AD-Miner terminé mais rapport introuvable.")

    target_dir = client_path / "ad-miner"
    # Copy to a temp dir first, then atomically swap — évite les ENOTEMPTY
    # si l'ancien dossier est verrouillé ou partiellement supprimé.
    tmp_dir = target_dir.parent / f".ad-miner-tmp-{clean_slug}"
    if tmp_dir.exists():
        shutil.rmtree(tmp_dir)
    shutil.copytree(render_dir, tmp_dir)
    if target_dir.exists():
        shutil.rmtree(target_dir)
    tmp_dir.rename(target_dir)

    warning = ""
    if result.returncode != 0:
        warning = " (avec avertissements Neo4j)"

    return {"status": "ok", "message": f"Rapport AD-Miner généré{warning}.", "url": f"/{clean_slug}/ad-miner/"}


# ─── Background tasks ─────────────────────────────────────────────────────────

def _full_audit_background(job_id: str, clean_name: str, clean_slug: str, pc_bytes: bytes, sh_bytes: bytes):
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
        write_bloodhound_status(clean_slug, clean_name, sh_src.name, upload_result.get("upload_id", ""))
        log_event(clean_slug, f"bloodhound_ingest_started upload_id={upload_result.get('upload_id')}")

        job_step(job_id, "Attente de la fin de l'ingestion BloodHound...")
        wait_for_bloodhound_ingestion(job_id=job_id, max_wait=600)
        log_event(clean_slug, "bloodhound_ingest_finished")

        job_step(job_id, "Génération AD-Miner en cours (peut prendre plusieurs minutes)...")
        ad_result = generate_ad_miner_for_client(clean_slug)
        log_event(clean_slug, "ad_miner_generated")

        # Mise à jour de la date du dernier audit complet
        write_client_metadata(client_path, clean_name, clean_slug,
                               extra={"last_audit_at": datetime.now().strftime("%d/%m/%Y %H:%M")})

        job_done(job_id, f"Audit complet terminé pour {clean_name}.", {
            "slug": clean_slug,
            "pingcastle_url": f"/{clean_slug}/pingcastle/",
            "ad_miner_url": f"/{clean_slug}/ad-miner/",
        })

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


# ─── API routes ───────────────────────────────────────────────────────────────

@app.get("/api/audits")
def audits():
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
        result.append({
            "slug": slug,
            "name": metadata.get("name") or slug.replace("-", " ").replace("_", " ").title(),
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
                "sharphound_date": latest_file_date(client_path / "sources" / "sharphound"),
                "sharphound_count": count_sharphound_zips(client_path),
                "pingcastle_date": latest_file_date(client_path / "sources" / "pingcastle"),
            },
            "bloodhound_active": bh_active_slug == slug,
        })
    return result


@app.get("/api/bloodhound/status")
def get_bloodhound_status():
    return read_bloodhound_status()


@app.get("/api/jobs/{job_id}")
def get_job(job_id: str):
    with _jobs_lock:
        if job_id not in _jobs:
            raise HTTPException(status_code=404, detail="Job introuvable.")
        return dict(_jobs[job_id])


@app.post("/api/clients")
def create_client(name: str = Form(...), slug: str = Form(...)):
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
    return {"status": "ok", "message": f"Client « {clean_name} » créé.", "slug": clean_slug}


@app.delete("/api/clients/{slug}")
def delete_client(slug: str):
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
async def upload_pingcastle(slug: str, report: UploadFile = File(...)):
    clean_slug = sanitize_slug(slug)
    client_path = ROOT / clean_slug
    if not client_path.exists():
        raise HTTPException(status_code=404, detail="Client introuvable.")
    filename = report.filename or ""
    if not filename.lower().endswith((".html", ".htm")):
        raise HTTPException(status_code=400, detail="Le rapport PingCastle doit être un fichier HTML.")
    ensure_client_dirs(client_path)
    ts = now_slug()
    source_file = client_path / "sources" / "pingcastle" / f"pingcastle_{ts}.html"
    target_file = client_path / "pingcastle" / "index.html"
    content = await report.read()
    if len(content) > MAX_PINGCASTLE_SIZE:
        raise HTTPException(status_code=413, detail="Fichier trop volumineux (max 50 Mo).")
    source_file.write_bytes(content)
    target_file.write_bytes(content)
    log_event(clean_slug, f"pingcastle_uploaded file={source_file.name}")
    return {"status": "ok", "message": "Rapport PingCastle importé.", "url": f"/{clean_slug}/pingcastle/"}


@app.post("/api/clients/{slug}/sharphound")
async def upload_sharphound_only(slug: str, zip_file: UploadFile = File(...)):
    clean_slug = sanitize_slug(slug)
    client_path = ROOT / clean_slug
    if not client_path.exists():
        raise HTTPException(status_code=404, detail="Client introuvable.")
    filename = zip_file.filename or ""
    if not filename.lower().endswith(".zip"):
        raise HTTPException(status_code=400, detail="Le fichier SharpHound doit être une archive ZIP.")
    ensure_client_dirs(client_path)
    ts = now_slug()
    source_file = client_path / "sources" / "sharphound" / f"sharphound_{ts}.zip"
    content = await zip_file.read()
    if len(content) > MAX_SHARPHOUND_SIZE:
        raise HTTPException(status_code=413, detail="Fichier trop volumineux (max 500 Mo).")
    source_file.write_bytes(content)
    log_event(clean_slug, f"sharphound_uploaded file={source_file.name}")
    upload_result = upload_sharphound_to_bloodhound(source_file)
    name = client_display_name(client_path, clean_slug)
    write_bloodhound_status(clean_slug, name, source_file.name, upload_result.get("upload_id", ""))
    log_event(clean_slug, f"bloodhound_ingest_started upload_id={upload_result.get('upload_id')}")
    return {"status": "ok", "message": "ZIP SharpHound importé dans BloodHound.", "bloodhound": upload_result}


@app.get("/api/clients/{slug}/sharphound/files")
def list_sharphound_files(slug: str):
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
            "date": datetime.fromtimestamp(f.stat().st_mtime).strftime("%d/%m/%Y %H:%M"),
        }
        for f in files
    ]


@app.get("/api/clients/{slug}/sharphound/download/{filename}")
def download_sharphound(slug: str, filename: str):
    clean_slug = sanitize_slug(slug)
    if not filename.lower().endswith(".zip") or "/" in filename or "\\" in filename or ".." in filename:
        raise HTTPException(status_code=400, detail="Nom de fichier invalide.")
    file_path = ROOT / clean_slug / "sources" / "sharphound" / filename
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="Fichier introuvable.")
    return FileResponse(path=str(file_path), filename=filename, media_type="application/zip")


@app.post("/api/clients/{slug}/ad-miner/generate")
def generate_ad_miner(slug: str):
    clean_slug = sanitize_slug(slug)
    client_path = ROOT / clean_slug
    if not client_path.exists():
        raise HTTPException(status_code=404, detail="Client introuvable.")
    job_id = create_job(f"AD-Miner — {clean_slug}")
    t = threading.Thread(target=_ad_miner_background, args=(job_id, clean_slug), daemon=True)
    t.start()
    return {"job_id": job_id, "status": "running"}


@app.post("/api/audits/full")
async def create_full_audit(
    name: str = Form(...),
    slug: str = Form(...),
    pingcastle_report: UploadFile = File(...),
    sharphound_zip: UploadFile = File(...),
):
    clean_slug = sanitize_slug(slug)
    clean_name = name.strip()
    if not clean_name:
        raise HTTPException(status_code=400, detail="Nom client invalide.")
    pc_name = pingcastle_report.filename or ""
    sh_name = sharphound_zip.filename or ""
    if not pc_name.lower().endswith((".html", ".htm")):
        raise HTTPException(status_code=400, detail="Le rapport PingCastle doit être un fichier HTML.")
    if not sh_name.lower().endswith(".zip"):
        raise HTTPException(status_code=400, detail="Le fichier SharpHound doit être une archive ZIP.")

    pc_bytes = await pingcastle_report.read()
    sh_bytes = await sharphound_zip.read()

    if len(pc_bytes) > MAX_PINGCASTLE_SIZE:
        raise HTTPException(status_code=413, detail="Fichier trop volumineux (max 50 Mo).")
    if len(sh_bytes) > MAX_SHARPHOUND_SIZE:
        raise HTTPException(status_code=413, detail="Fichier trop volumineux (max 500 Mo).")

    job_id = create_job(f"Audit complet — {clean_name}")
    t = threading.Thread(
        target=_full_audit_background,
        args=(job_id, clean_name, clean_slug, pc_bytes, sh_bytes),
        daemon=True,
    )
    t.start()
    return {"job_id": job_id, "status": "running", "message": f"Audit lancé pour {clean_name}."}


@app.post("/api/bloodhound/reset")
def reset_bloodhound():
    try:
        log_event("_system", "bloodhound_reset_started")
        down = run_bloodhound_compose(["down", "-v"])
        if down.returncode != 0:
            raise HTTPException(status_code=500, detail=f"Erreur docker compose down -v : {down.stderr}")
        up = run_bloodhound_compose(["up", "-d"])
        if up.returncode != 0:
            raise HTTPException(status_code=500, detail=f"Erreur docker compose up -d : {up.stderr}")
        clear_bloodhound_status()
        log_event("_system", "bloodhound_reset_done")
        return {"status": "ok", "message": "BloodHound a été vidé et redémarré."}
    except subprocess.TimeoutExpired:
        raise HTTPException(status_code=500, detail="Timeout pendant la réinitialisation BloodHound.")
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
                results["errors"].append(f"BloodHound: Authentification échouée ({r.status_code})")
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
