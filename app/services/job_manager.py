import uuid
from datetime import datetime, timezone
from typing import Any, Optional
from app.models.domain import JobRecord, JobStatus


class JobManager:
    """In-memory job tracker for managing classification job lifecycles."""

    def __init__(self) -> None:
        self._jobs: dict[str, JobRecord] = {}

    def create_job(self) -> JobRecord:
        job_id = str(uuid.uuid4())
        job = JobRecord(job_id=job_id, status=JobStatus.PENDING)
        self._jobs[job_id] = job
        return job

    def update_status(
        self,
        job_id: str,
        status: JobStatus,
        error_message: Optional[str] = None,
    ) -> Optional[JobRecord]:
        job = self._jobs.get(job_id)
        if not job:
            return None
        job.status = status
        job.updated_at = datetime.now(timezone.utc)
        if error_message is not None:
            job.error_message = error_message
        return job

    def get_job(self, job_id: str) -> Optional[JobRecord]:
        return self._jobs.get(job_id)

    def mark_failed(
        self, job_id: str, error_message: str
    ) -> Optional[JobRecord]:
        return self.update_status(
            job_id, status=JobStatus.FAILED, error_message=error_message
        )

    def mark_completed(
        self, job_id: str, result: Optional[dict[str, Any]] = None
    ) -> Optional[JobRecord]:
        job = self._jobs.get(job_id)
        if not job:
            return None
        job.status = JobStatus.COMPLETED
        job.updated_at = datetime.now(timezone.utc)
        if result is not None:
            job.result = result
        return job


job_manager = JobManager()
