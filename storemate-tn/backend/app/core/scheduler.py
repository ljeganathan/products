import fcntl
import logging
from typing import IO

from apscheduler.schedulers.asyncio import AsyncIOScheduler

from app.services.dashboard_digest_service import run_daily_digest_emails
from app.services.notification_service import run_low_stock_scan

logger = logging.getLogger(__name__)

scheduler = AsyncIOScheduler()

# Production runs multiple gunicorn+uvicorn worker processes
# (docker-compose.prod.yml) — without this guard, every worker would start
# its own APScheduler and the low-stock scan / digest email would fire once
# per worker. A non-blocking exclusive file lock is the boring, no-new-infra
# way to pick exactly one worker as the scheduler owner: the first worker to
# open+lock the file wins, every other worker's lock attempt fails
# immediately and that worker simply skips starting the scheduler. The lock
# is released automatically when the owning process exits (kernel cleans up
# the fd) — no explicit unlock needed for a long-lived server process.
_SCHEDULER_LOCK_PATH = "/tmp/storemate_scheduler.lock"
_lock_file: IO[str] | None = None


def _acquire_scheduler_lock() -> bool:
    global _lock_file
    _lock_file = open(_SCHEDULER_LOCK_PATH, "w")
    try:
        fcntl.flock(_lock_file, fcntl.LOCK_EX | fcntl.LOCK_NB)
        return True
    except OSError:
        _lock_file.close()
        _lock_file = None
        return False


async def _low_stock_job() -> None:
    try:
        count = await run_low_stock_scan()
        if count:
            logger.info("Low-stock scan created %d notification(s)", count)
    except Exception:
        logger.exception("Low-stock scan job failed")


async def _daily_digest_job() -> None:
    try:
        sent = await run_daily_digest_emails()
        logger.info("Daily digest job sent %d email(s)", sent)
    except Exception:
        logger.exception("Daily digest job failed")


def start_scheduler() -> None:
    if not _acquire_scheduler_lock():
        logger.info(
            "Scheduler lock held by another worker process — skipping in this process"
        )
        return

    scheduler.add_job(
        _low_stock_job, "interval", minutes=15, id="low_stock_scan", replace_existing=True
    )
    scheduler.add_job(
        _daily_digest_job, "cron", hour=8, minute=0, id="daily_digest_email", replace_existing=True
    )
    scheduler.start()


def shutdown_scheduler() -> None:
    global _lock_file
    if scheduler.running:
        scheduler.shutdown(wait=False)
    if _lock_file is not None:
        _lock_file.close()
        _lock_file = None
