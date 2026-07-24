import fcntl

from app.core import scheduler as scheduler_module


def test_acquire_scheduler_lock_fails_when_already_held() -> None:
    blocker = open(scheduler_module._SCHEDULER_LOCK_PATH, "w")
    fcntl.flock(blocker, fcntl.LOCK_EX | fcntl.LOCK_NB)
    try:
        assert scheduler_module._acquire_scheduler_lock() is False
        assert scheduler_module._lock_file is None
    finally:
        blocker.close()


def test_acquire_scheduler_lock_succeeds_when_free() -> None:
    acquired = scheduler_module._acquire_scheduler_lock()
    try:
        assert acquired is True
        assert scheduler_module._lock_file is not None
    finally:
        if scheduler_module._lock_file is not None:
            scheduler_module._lock_file.close()
            scheduler_module._lock_file = None


def test_start_scheduler_skips_when_lock_unavailable(monkeypatch) -> None:
    monkeypatch.setattr(scheduler_module, "_acquire_scheduler_lock", lambda: False)
    scheduler_module.start_scheduler()
    assert scheduler_module.scheduler.running is False


def test_start_and_shutdown_scheduler_when_lock_acquired() -> None:
    # Uses the real file lock (no monkeypatch) so shutdown_scheduler() also
    # exercises closing/clearing the actual lock file, not a stubbed-out one.
    try:
        scheduler_module.start_scheduler()
        assert scheduler_module.scheduler.running is True
        assert scheduler_module.scheduler.get_job("low_stock_scan") is not None
        assert scheduler_module.scheduler.get_job("daily_digest_email") is not None
    finally:
        scheduler_module.shutdown_scheduler()
        # APScheduler's shutdown() flips `running` asynchronously via the
        # event loop, not synchronously on return — the lock-file release is
        # the part this test (and the multi-worker guard) actually cares
        # about, so assert that instead of racing it.
        assert scheduler_module._lock_file is None
