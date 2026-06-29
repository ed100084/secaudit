"""
稽核發現報告 API — SSE 串流產生
"""
import asyncio
import json
import re
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import StreamingResponse

from db import (
    get_project, get_questions, save_findings,
    create_generation_job, update_generation_job, get_generation_job,
    get_active_generation_job,
)
from llm_service import stream_findings
from routers import verify_api_key

router = APIRouter(tags=["findings"])


def _now_iso():
    return datetime.now(timezone.utc).isoformat()


def _build_responses(questions: list) -> list:
    return [
        {
            "question_id": q["id"],
            "response_text": q.get("response_text", ""),
            "compliance_status": q.get("compliance_status"),
            "auditor_notes": q.get("auditor_notes", ""),
        }
        for q in questions
    ]


async def _build_findings_for_project(project_id: str, report_format: str) -> dict:
    project = get_project(project_id)
    if not project:
        raise RuntimeError("Project not found")

    questions = get_questions(project_id)
    if not questions:
        raise RuntimeError("No questions found")

    buffer = []
    repaired = None
    async for event in stream_findings(project, questions, _build_responses(questions), report_format=report_format):
        for line in event.splitlines():
            if not line.startswith("data: "):
                continue
            payload = line[6:]
            if payload == "[DONE]":
                continue
            data = json.loads(payload)
            if data.get("repair"):
                repaired = data["repair"]
            else:
                buffer.append(data.get("chunk", ""))

    raw = (repaired or "".join(buffer)).strip()
    raw = re.sub(r"^```(?:json)?\s*", "", raw)
    raw = re.sub(r"\s*```$", "", raw)
    report_data = json.loads(raw)
    save_findings(project_id, report_format, report_data)
    return report_data


async def _run_finding_job(job_id: str, project_id: str, report_format: str):
    try:
        update_generation_job(job_id, {
            "status": "running",
            "message": "Generating audit report",
            "updated_at": _now_iso(),
        })
        report_data = await _build_findings_for_project(project_id, report_format)
        update_generation_job(job_id, {
            "status": "done",
            "message": "Report generated",
            "finding_count": len(report_data.get("findings", [])) if isinstance(report_data, dict) else 0,
            "finished_at": _now_iso(),
        })
    except Exception as exc:
        update_generation_job(job_id, {
            "status": "error",
            "message": str(exc),
            "finished_at": _now_iso(),
        })


@router.get("/projects/{project_id}/findings/stream")
async def api_stream_findings(
    project_id: str,
    format: str = Query("iia5c"),
    api_key: str = Query(None),
):
    # SSE 用 query param 驗證
    from config import settings
    if not api_key or api_key != settings.API_KEY:
        raise HTTPException(401, "Invalid API key")

    project = get_project(project_id)
    if not project:
        raise HTTPException(404, "Project not found")

    questions = get_questions(project_id)
    if not questions:
        raise HTTPException(400, "No questions found")

    return StreamingResponse(
        stream_findings(project, questions, _build_responses(questions), report_format=format),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


@router.post("/projects/{project_id}/findings/jobs")
async def api_start_finding_job(project_id: str, format: str = Query("iia5c")):
    if not get_project(project_id):
        raise HTTPException(404, "Project not found")
    if not get_questions(project_id):
        raise HTTPException(400, "No questions found")

    active = get_active_generation_job(project_id, "report", format=format)
    if active:
        return active

    job_id = str(uuid.uuid4())
    job = create_generation_job(job_id, project_id, "report", message="Queued", format=format)
    asyncio.create_task(_run_finding_job(job_id, project_id, format))
    return job


@router.get("/finding-jobs/{job_id}")
def api_get_finding_job(job_id: str):
    job = get_generation_job(job_id)
    if not job:
        raise HTTPException(404, "Job not found")
    return job


@router.get("/projects/{project_id}/findings")
async def api_get_findings(project_id: str):
    from db import get_findings
    if not get_project(project_id):
        raise HTTPException(404, "Project not found")
    return get_findings(project_id)
