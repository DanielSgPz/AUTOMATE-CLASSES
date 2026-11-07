from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import Body, FastAPI, HTTPException, Query, Response
from fastapi.responses import HTMLResponse

from main import workflow_principal
from services.automation_runtime import automation_lock
from services.discovery_service import (
    discover_assignment_options,
    discover_pending_items,
    discover_study_plans,
)
from services.playwright_runner import run_playwright_task
from services.github_profile_service import (
    github_status,
    publish_profile,
    save_github_config,
)
from services.scheduler_service import (
    configure_job,
    delete_job,
    pause_job,
    scheduler_status,
)
from utils.credentials import save_smart_credentials, smart_credentials_status
from utils.profile import ProgrammingProfile, load_profile, save_profile


@asynccontextmanager
async def lifespan(_app: FastAPI):
    yield


app = FastAPI(title="AUTOMATE-CLASSES", version="3.0.0", lifespan=lifespan)
_index_path = Path(__file__).resolve().parent / "web" / "index.html"


@app.get("/", response_class=HTMLResponse)
async def index():
    return _index_path.read_text(encoding="utf-8")


@app.get("/health")
async def health():
    return {"status": "ok", "scheduler": scheduler_status()}


@app.get("/favicon.ico", include_in_schema=False)
async def favicon():
    return Response(status_code=204)


@app.get("/api/credentials")
async def get_credentials():
    return smart_credentials_status()


@app.put("/api/credentials")
async def update_credentials(payload: dict = Body(...)):
    try:
        save_smart_credentials(
            url=str(payload.get("url", "")),
            username=str(payload.get("username", "")),
            password=payload.get("password") or None,
        )
        return {"ok": True, **smart_credentials_status()}
    except Exception as error:
        raise HTTPException(status_code=422, detail=_error_message(error)) from error


@app.post("/api/explore/plans")
async def explore_plans():
    return {"plans": await _playwright_operation(discover_study_plans)}


@app.post("/api/explore/pending")
async def explore_pending(payload: dict = Body(...)):
    study_plan = str(payload.get("study_plan", "")).strip()
    if not study_plan:
        raise HTTPException(status_code=422, detail="Selecciona primero un plan de estudios.")
    return {"items": await _playwright_operation(discover_pending_items, study_plan)}


@app.post("/api/explore/options")
async def explore_options(payload: dict = Body(...)):
    study_plan = str(payload.get("study_plan", "")).strip()
    item_key = str(payload.get("item_key", "")).strip()
    if not study_plan or not item_key:
        raise HTTPException(status_code=422, detail="El plan y el ítem son obligatorios.")
    return await _playwright_operation(discover_assignment_options, study_plan, item_key)


@app.get("/api/profile")
async def get_profile():
    return load_profile().to_dict()


@app.put("/api/profile")
async def update_profile(payload: dict = Body(...)):
    try:
        profile = ProgrammingProfile.from_dict(payload)
        path = save_profile(profile)
        github = publish_profile(profile.to_dict())
        return {"ok": True, "path": str(path), "profile": profile.to_dict(), "github": github}
    except Exception as error:
        raise HTTPException(status_code=422, detail=_error_message(error)) from error


@app.get("/api/github")
async def get_github_config():
    return github_status()


@app.put("/api/github")
async def update_github_config(payload: dict = Body(...)):
    try:
        status = save_github_config(
            repository=str(payload.get("repository", "")),
            token=payload.get("token") or None,
        )
        publication = publish_profile(load_profile().to_dict())
        return {"ok": True, **status, **publication}
    except Exception as error:
        raise HTTPException(status_code=422, detail=_error_message(error)) from error


@app.get("/api/scheduler")
async def get_scheduler():
    return scheduler_status()


@app.post("/api/scheduler/start")
async def enable_scheduler(payload: dict = Body(default={})):
    try:
        return configure_job(payload.get("run_time") or load_profile().run_time)
    except Exception as error:
        raise HTTPException(status_code=422, detail=_error_message(error)) from error


@app.post("/api/scheduler/pause")
async def disable_scheduler():
    return pause_job()


@app.delete("/api/scheduler")
async def remove_scheduler():
    return delete_job()


@app.post("/api/run")
async def run_automation(confirm: bool = Query(False)):
    if not confirm:
        raise HTTPException(status_code=400, detail="Confirma explícitamente la ejecución real.")
    return await _run(dry_run=False)


@app.post("/api/dry-run")
async def dry_run():
    return await _run(dry_run=True)


async def _playwright_operation(callable_, *args):
    if automation_lock.locked():
        raise HTTPException(status_code=409, detail="Ya existe una operación de Smart en curso.")
    async with automation_lock:
        try:
            return await run_playwright_task(callable_, *args)
        except Exception as error:
            raise HTTPException(status_code=502, detail=_error_message(error)) from error


async def _run(dry_run: bool):
    report = await _playwright_operation(workflow_principal, None, dry_run)
    return {"ok": report.get("estado") == "exito", "report": report}


def _error_message(error: Exception) -> str:
    message = str(error).strip()
    return message or error.__class__.__name__
