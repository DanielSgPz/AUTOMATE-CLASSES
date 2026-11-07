import json
from datetime import datetime
from pathlib import Path

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from zoneinfo import ZoneInfo

from main import workflow_principal
from services.automation_runtime import automation_lock
from services.playwright_runner import run_playwright_task
from utils.profile import load_profile


STATE_PATH = Path(__file__).resolve().parent.parent / "config" / "scheduler_state.json"
JOB_ID = "automate-classes-daily"
COLOMBIA_TZ = ZoneInfo("America/Bogota")
scheduler = AsyncIOScheduler(timezone=COLOMBIA_TZ)


def load_scheduler_state() -> dict:
    if not STATE_PATH.exists():
        return {"enabled": False, "run_time": load_profile().run_time, "last_run": None, "last_status": None}
    return json.loads(STATE_PATH.read_text(encoding="utf-8"))


def save_scheduler_state(state: dict) -> None:
    STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    STATE_PATH.write_text(
        json.dumps(state, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


async def scheduled_run():
    state = load_scheduler_state()
    state["last_run"] = datetime.now(COLOMBIA_TZ).isoformat()
    state["last_status"] = "running"
    save_scheduler_state(state)
    try:
        async with automation_lock:
            report = await run_playwright_task(workflow_principal, None, False, True)
            state["last_status"] = report.get("estado", "unknown")
    except Exception as error:
        state["last_status"] = "error"
        state["last_error"] = str(error)
    finally:
        save_scheduler_state(state)


def configure_job(run_time: str | None = None, enabled: bool = True) -> dict:
    profile = load_profile()
    time_value = run_time or profile.run_time
    hour, minute = (int(value) for value in time_value.split(":"))
    scheduler.add_job(
        scheduled_run,
        CronTrigger(hour=hour, minute=minute, timezone=COLOMBIA_TZ),
        id=JOB_ID,
        replace_existing=True,
        max_instances=1,
        coalesce=True,
    )
    state = load_scheduler_state()
    state.update({"enabled": enabled, "run_time": time_value})
    save_scheduler_state(state)
    return scheduler_status()


def pause_job() -> dict:
    if scheduler.get_job(JOB_ID):
        scheduler.remove_job(JOB_ID)
    state = load_scheduler_state()
    state["enabled"] = False
    save_scheduler_state(state)
    return scheduler_status()


def delete_job() -> dict:
    if scheduler.get_job(JOB_ID):
        scheduler.remove_job(JOB_ID)
    if STATE_PATH.exists():
        STATE_PATH.unlink()
    return scheduler_status()


def scheduler_status() -> dict:
    state = load_scheduler_state()
    job = scheduler.get_job(JOB_ID) if scheduler.running else None
    state["active"] = bool(job)
    state["next_run"] = job.next_run_time.isoformat() if job and job.next_run_time else None
    return state


def start_scheduler() -> None:
    if not scheduler.running:
        scheduler.start()
    state = load_scheduler_state()
    if state.get("enabled"):
        configure_job(state.get("run_time"), enabled=True)


def shutdown_scheduler() -> None:
    if scheduler.running:
        scheduler.shutdown(wait=False)
