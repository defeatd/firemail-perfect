"""
大批量导入后台首验任务注册表（ImportJobRegistry）。

职责：
- 批量导入请求先落库（auth_status='pending'）并在毫秒级返回 job_id
- 本模块在后台线程池中以受控并发与令牌桶限速逐个调用 OutlookTokenService.rotate(trigger="import")
- 实时维护计数与非 ok 明细（含中文处理建议），定期通过 notifier 推送 import_progress
- 支持查询权限隔离（属主/管理员）、取消未开始任务（保持 pending 交由 TokenKeeper 兜底）与优雅停机
- 严禁在日志或快照中泄露任何密码、refresh_token 或 access_token
"""

from __future__ import annotations

import concurrent.futures
import os
import threading
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Sequence

from .logger import logger
from .token_service import get_token_service, hint_for, sanitize_error_text

MAX_JOB_RESULTS = 1000
JOB_RETENTION_SECONDS = 24 * 3600
MAX_JOBS_PER_USER = 20


def _parse_concurrency_env(default: int = 4) -> int:
    raw = os.environ.get("OUTLOOK_IMPORT_VERIFY_CONCURRENCY", "").strip()
    if not raw:
        return default
    try:
        val = int(raw)
    except ValueError:
        logger.warning(
            "环境变量 OUTLOOK_IMPORT_VERIFY_CONCURRENCY=%r 无效，使用默认值 %d",
            raw,
            default,
        )
        return default
    return max(1, min(8, val))


def _parse_rps_env(default: float = 4.0) -> float:
    raw = os.environ.get("OUTLOOK_IMPORT_VERIFY_RPS", "").strip()
    if not raw:
        return default
    try:
        val = float(raw)
    except ValueError:
        logger.warning(
            "环境变量 OUTLOOK_IMPORT_VERIFY_RPS=%r 无效，使用默认值 %.1f",
            raw,
            default,
        )
        return default
    return max(0.2, min(50.0, val))


class _TokenBucket:
    """线程安全令牌桶限速器，支持取消事件即时打断等待。"""

    def __init__(self, rate: float):
        self.rate = max(0.1, float(rate))
        self.capacity = max(1.0, self.rate)
        self._tokens = self.capacity
        self._last = time.monotonic()
        self._lock = threading.Lock()

    def acquire(
        self,
        cancel_event: threading.Event,
        shutdown_event: threading.Event,
    ) -> bool:
        while not cancel_event.is_set() and not shutdown_event.is_set():
            with self._lock:
                now = time.monotonic()
                elapsed = max(0.0, now - self._last)
                self._last = now
                self._tokens = min(self.capacity, self._tokens + elapsed * self.rate)
                if self._tokens >= 1.0:
                    self._tokens -= 1.0
                    return True
                wait_s = (1.0 - self._tokens) / self.rate
            sleep_s = min(wait_s, 0.1)
            if cancel_event.wait(timeout=sleep_s) or shutdown_event.is_set():
                return False
        return False


@dataclass
class ImportJob:
    id: str
    user_id: int
    email_ids: List[int]
    total: int
    done: int = 0
    ok: int = 0
    need_reauth: int = 0
    banned: int = 0
    failed: int = 0
    deferred: int = 0
    cancelled: bool = False
    finished: bool = False
    created_at: float = field(default_factory=time.time)
    finished_at: Optional[float] = None
    results: List[Dict[str, Any]] = field(default_factory=list)
    _cancel_event: threading.Event = field(default_factory=threading.Event, repr=False)


class ImportJobRegistry:
    """进程内大批量导入首验任务调度与状态存储。"""

    def __init__(
        self,
        db,
        *,
        concurrency: Optional[int] = None,
        rps: Optional[float] = None,
        service_factory: Callable = get_token_service,
        notifier: Optional[Callable[[int, Dict[str, Any]], None]] = None,
    ):
        self.db = db
        if concurrency is not None:
            self.concurrency = max(1, min(8, int(concurrency)))
        else:
            self.concurrency = _parse_concurrency_env(4)

        if rps is not None:
            self.rps = max(0.1, float(rps))
        else:
            self.rps = _parse_rps_env(4.0)

        self.service_factory = service_factory
        self._notifier = notifier
        self._bucket = _TokenBucket(self.rps)
        self._lock = threading.Lock()
        self._jobs: Dict[str, ImportJob] = {}
        self._shutdown_event = threading.Event()
        self._executor: Optional[concurrent.futures.ThreadPoolExecutor] = None
        self._executor_lock = threading.Lock()

    def set_notifier(
        self, notifier: Optional[Callable[[int, Dict[str, Any]], None]]
    ) -> None:
        self._notifier = notifier

    def _get_executor(self) -> concurrent.futures.ThreadPoolExecutor:
        with self._executor_lock:
            if self._executor is None:
                self._executor = concurrent.futures.ThreadPoolExecutor(
                    max_workers=self.concurrency,
                    thread_name_prefix="ImportVerify",
                )
            return self._executor

    def _prune_locked(self, now_ts: float) -> None:
        # 1. 淘汰超过 24h 的已结束任务
        expired = [
            jid
            for jid, job in self._jobs.items()
            if job.finished
            and job.finished_at is not None
            and (now_ts - job.finished_at) > JOB_RETENTION_SECONDS
        ]
        for jid in expired:
            self._jobs.pop(jid, None)

        # 2. 每用户最多保留 20 个任务（优先淘汰最旧的已结束任务）
        by_user: Dict[int, List[ImportJob]] = {}
        for job in self._jobs.values():
            by_user.setdefault(job.user_id, []).append(job)

        for user_jobs in by_user.values():
            if len(user_jobs) <= MAX_JOBS_PER_USER:
                continue
            finished_sorted = sorted(
                (j for j in user_jobs if j.finished),
                key=lambda j: j.created_at,
            )
            overflow = len(user_jobs) - MAX_JOBS_PER_USER
            for j in finished_sorted[:overflow]:
                self._jobs.pop(j.id, None)

    def start(self, user_id: int, email_ids: Sequence[int]) -> Optional[ImportJob]:
        """创建并启动后台首验任务；空列表返回 None。"""
        unique_ids: List[int] = []
        seen: set[int] = set()
        for raw_id in email_ids:
            try:
                eid = int(raw_id)
            except (TypeError, ValueError):
                continue
            if eid > 0 and eid not in seen:
                seen.add(eid)
                unique_ids.append(eid)

        if not unique_ids:
            return None

        job = ImportJob(
            id=uuid.uuid4().hex,
            user_id=int(user_id),
            email_ids=unique_ids,
            total=len(unique_ids),
        )
        with self._lock:
            self._prune_locked(time.time())
            self._jobs[job.id] = job

        driver = threading.Thread(
            target=self._run_job,
            args=(job,),
            name=f"ImportJob-{job.id[:8]}",
            daemon=True,
        )
        driver.start()
        logger.info(
            "启动批量导入首验任务 job_id=%s user_id=%d total=%d concurrency=%d rps=%.1f",
            job.id,
            job.user_id,
            job.total,
            self.concurrency,
            self.rps,
        )
        return job

    def get(
        self, job_id: str, *, user_id: int, is_admin: bool
    ) -> Optional[ImportJob]:
        with self._lock:
            job = self._jobs.get(str(job_id))
            if job is None:
                return None
            if not is_admin and job.user_id != int(user_id):
                return None
            return job

    def cancel(self, job_id: str, *, user_id: int, is_admin: bool) -> bool:
        with self._lock:
            job = self._jobs.get(str(job_id))
            if job is None:
                return False
            if not is_admin and job.user_id != int(user_id):
                return False
            if job.finished:
                return False
            job.cancelled = True
            job._cancel_event.set()
            logger.info("批量导入首验任务已请求取消 job_id=%s", job.id)
            return True

    def snapshot(self, job: ImportJob) -> Dict[str, Any]:
        with self._lock:
            return {
                "id": job.id,
                "job_id": job.id,
                "total": job.total,
                "done": job.done,
                "ok": job.ok,
                "need_reauth": job.need_reauth,
                "banned": job.banned,
                "failed": job.failed,
                "deferred": job.deferred,
                "cancelled": job.cancelled,
                "finished": job.finished,
                "created_at": job.created_at,
                "finished_at": job.finished_at,
                "results": list(job.results),
            }

    def _emit_progress(self, job: ImportJob) -> None:
        notifier = self._notifier
        if notifier is None:
            return
        try:
            payload = {"type": "import_progress", **self.snapshot(job)}
            notifier(job.user_id, payload)
        except Exception as exc:
            logger.warning(
                "推送首验进度失败 job_id=%s: %s",
                job.id,
                sanitize_error_text(str(exc), 160),
            )

    def _verify_one(self, job: ImportJob, email_id: int) -> None:
        if job._cancel_event.is_set() or self._shutdown_event.is_set():
            return
        if not self._bucket.acquire(job._cancel_event, self._shutdown_event):
            return
        if job._cancel_event.is_set() or self._shutdown_event.is_set():
            return

        service = self.service_factory(self.db)
        try:
            res = service.rotate(email_id, trigger="import", include_invalid=True)
        except Exception as exc:
            logger.warning(
                "首验邮箱 ID=%d 异常: %s",
                email_id,
                sanitize_error_text(str(exc), 200),
            )
            res = None

        email_addr = ""
        try:
            state = self.db.get_outlook_token_state(email_id)
            if state:
                email_addr = str(state.get("email") or "")
        except Exception:
            email_addr = ""

        should_notify = False
        with self._lock:
            job.done += 1
            if res is not None and res.success:
                job.ok += 1
            else:
                err_code = (
                    (res.error_code or res.error_kind or "unknown")
                    if res is not None
                    else "exception"
                )
                if res is not None and res.error_code == "client_suspended":
                    job.deferred += 1
                    item_status = "deferred"
                elif res is not None and (
                    res.error_kind == "banned" or res.error_code == "banned"
                ):
                    job.banned += 1
                    item_status = "banned"
                elif res is not None and res.need_reauth:
                    job.need_reauth += 1
                    item_status = "need_reauth"
                else:
                    job.failed += 1
                    item_status = "failed"

                if len(job.results) < MAX_JOB_RESULTS:
                    job.results.append(
                        {
                            "email_id": email_id,
                            "email": email_addr,
                            "status": item_status,
                            "error_code": err_code,
                            "hint": hint_for(err_code),
                        }
                    )

            if job.done % 10 == 0:
                should_notify = True

        if should_notify:
            self._emit_progress(job)

    def _run_job(self, job: ImportJob) -> None:
        executor = self._get_executor()
        futures: List[concurrent.futures.Future] = []
        try:
            for eid in job.email_ids:
                if job._cancel_event.is_set() or self._shutdown_event.is_set():
                    break
                try:
                    fut = executor.submit(self._verify_one, job, eid)
                    futures.append(fut)
                except RuntimeError:
                    break

            for fut in concurrent.futures.as_completed(futures):
                try:
                    fut.result()
                except concurrent.futures.CancelledError:
                    continue
                except Exception as exc:
                    logger.warning(
                        "首验任务子项异常 job_id=%s: %s",
                        job.id,
                        sanitize_error_text(str(exc), 160),
                    )
        finally:
            with self._lock:
                job.finished = True
                job.finished_at = time.time()
            logger.info(
                "批量导入首验完成 job_id=%s total=%d done=%d ok=%d need_reauth=%d banned=%d failed=%d deferred=%d cancelled=%s",
                job.id,
                job.total,
                job.done,
                job.ok,
                job.need_reauth,
                job.banned,
                job.failed,
                job.deferred,
                job.cancelled,
            )
            self._emit_progress(job)

    def shutdown(self) -> None:
        """优雅停机：取消尚未开始的首验任务并关闭线程池。"""
        self._shutdown_event.set()
        with self._lock:
            for job in self._jobs.values():
                if not job.finished:
                    job._cancel_event.set()

        with self._executor_lock:
            executor = self._executor
            self._executor = None
        if executor is not None:
            executor.shutdown(wait=False, cancel_futures=True)


_registry_singleton_lock = threading.Lock()
_registry_singleton: Optional[ImportJobRegistry] = None


def get_import_job_registry(db) -> ImportJobRegistry:
    """获取进程级 ImportJobRegistry 单例（若切换了 db 实例则重建以隔离测试）。"""
    global _registry_singleton
    with _registry_singleton_lock:
        if _registry_singleton is None or _registry_singleton.db is not db:
            _registry_singleton = ImportJobRegistry(db)
        return _registry_singleton
