import json
import os
import tempfile
import zipfile
from typing import Any, Dict
from fastapi import (
    APIRouter,
    BackgroundTasks,
    File,
    Form,
    HTTPException,
    UploadFile,
)
from fastapi.responses import FileResponse
from app.models.domain import JobCreateResponse, JobStatus, JobStatusResponse
from app.services import job_manager, orchestrator_service

router = APIRouter()


@router.post("/upload", response_model=JobCreateResponse, status_code=202)
async def upload_file(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    category_column: str = Form(...),
) -> JobCreateResponse:
    """Upload CSV/XLSX file, create a classification job, and run pipeline in background."""
    if not file.filename:
        raise HTTPException(status_code=400, detail="Filename is required.")

    ext = file.filename.lower().split(".")[-1]
    if ext not in ("csv", "txt", "xlsx", "xls"):
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file format: '.{ext}'. Supported formats: CSV, XLSX.",
        )

    # Save uploaded file to temporary path
    temp_dir = tempfile.gettempdir()
    temp_file_path = os.path.join(
        temp_dir, f"upload_{os.urandom(8).hex()}_{file.filename}"
    )

    try:
        content = await file.read()
        with open(temp_file_path, "wb") as f:
            f.write(content)
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to save uploaded file: {str(e)}"
        )

    # Create job record
    job = job_manager.create_job()

    # Dispatch background classification task
    background_tasks.add_task(
        orchestrator_service.run_classification_job,
        job_id=job.job_id,
        file_path=temp_file_path,
        category_column=category_column,
        cleanup_uploaded_file=True,
    )

    return JobCreateResponse(job_id=job.job_id, status=job.status)


@router.get("/job/{job_id}", response_model=JobStatusResponse)
def get_job_status(job_id: str) -> JobStatusResponse:
    """Get classification job status and result/error details."""
    job = job_manager.get_job(job_id)
    if not job:
        raise HTTPException(
            status_code=404, detail=f"Job with ID '{job_id}' not found."
        )

    return JobStatusResponse(
        job_id=job.job_id,
        status=job.status,
        created_at=job.created_at,
        updated_at=job.updated_at,
        error_message=job.error_message,
        result=job.result,
    )


@router.get("/download/{job_id}")
def download_job_result(job_id: str) -> FileResponse:
    """Download exported ZIP file for a completed job."""
    job = job_manager.get_job(job_id)
    if not job:
        raise HTTPException(
            status_code=404, detail=f"Job with ID '{job_id}' not found."
        )

    if job.status != JobStatus.COMPLETED:
        raise HTTPException(
            status_code=400,
            detail=f"Job '{job_id}' is currently in state '{job.status.value}'. Download is available when status is 'completed'.",
        )

    zip_path = (job.result or {}).get("zip_path")
    if not zip_path or not os.path.exists(zip_path):
        raise HTTPException(
            status_code=404,
            detail=f"Exported ZIP archive for job '{job_id}' not found on server.",
        )

    download_filename = f"job_{job_id}_export.zip"
    return FileResponse(
        path=zip_path,
        filename=download_filename,
        media_type="application/zip",
    )


@router.get("/job/{job_id}/files")
def get_job_manifest(job_id: str) -> Dict[str, Any]:
    """Retrieve manifest.json contents for a completed job."""
    job = job_manager.get_job(job_id)
    if not job:
        raise HTTPException(
            status_code=404, detail=f"Job with ID '{job_id}' not found."
        )

    if job.status != JobStatus.COMPLETED:
        raise HTTPException(
            status_code=400,
            detail=f"Job '{job_id}' is in state '{job.status.value}'. Manifest is available when status is 'completed'.",
        )

    zip_path = (job.result or {}).get("zip_path")
    if not zip_path or not os.path.exists(zip_path):
        raise HTTPException(
            status_code=404,
            detail=f"Exported ZIP archive for job '{job_id}' not found on server.",
        )

    try:
        with zipfile.ZipFile(zip_path, "r") as zipf:
            if "manifest.json" not in zipf.namelist():
                raise HTTPException(
                    status_code=404,
                    detail="manifest.json missing inside ZIP archive.",
                )
            manifest_bytes = zipf.read("manifest.json")
            return json.loads(manifest_bytes.decode("utf-8"))
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to read manifest.json: {str(e)}"
        )
