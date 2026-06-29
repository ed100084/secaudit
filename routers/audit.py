"""
稽核工作流 API — 框架選擇、範圍設定、問題產生、回覆記錄
"""
import asyncio
import shutil
import uuid
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, File, Form, HTTPException, UploadFile

from config import settings
from db import (
    get_project, update_project, save_questions, merge_generated_questions, get_questions,
    update_question, delete_question_by_id, add_question, get_quick_phrases,
    list_audit_frameworks, get_audit_framework, create_audit_framework,
    update_audit_framework, delete_audit_framework, list_audit_controls,
    create_audit_control, update_audit_control, delete_audit_control,
    create_generation_job, update_generation_job, get_generation_job,
    get_active_generation_job,
)
from models import (
    FrameworkSelection, ScopeInput, QuestionCreate, QuestionUpdate, QuestionPatch,
    ResponsesInput, AuditFrameworkCreate, AuditFrameworkUpdate,
    AuditControlCreate, AuditControlUpdate,
)
from frameworks import get_framework_options
from document_parser import parse_file
from llm_service import generate_questions as generate_llm_questions
from audit_templates import get_all_templates, get_template

router = APIRouter(tags=["audit"])


def _now_iso():
    return datetime.now(timezone.utc).isoformat()


async def _build_questions_for_project(project: dict, existing_questions: list | None = None) -> list:
    target_count = max(1, min(int(project.get("question_count") or 8), 30))
    return await generate_llm_questions(
        framework_ids=project.get("frameworks", []),
        custom_text=project.get("custom_framework_text", ""),
        scope=project.get("scope", ""),
        context=project.get("context", ""),
        responsibility_level=project.get("responsibility_level"),
        target_count=target_count,
        existing_questions=existing_questions,
    )


async def _run_question_job(job_id: str, project_id: str):
    try:
        project = get_project(project_id)
        if not project:
            raise RuntimeError("Project not found")
        update_generation_job(job_id, {
            "status": "running",
            "message": "Generating audit questions",
            "updated_at": _now_iso(),
        })
        existing = get_questions(project_id)
        questions = await _build_questions_for_project(project, existing_questions=existing)
        target_count = max(1, min(int(project.get("question_count") or len(questions) or 8), 30))
        questions = merge_generated_questions(project_id, questions, target_count)
        update_generation_job(job_id, {
            "status": "done",
            "message": "Questions generated",
            "question_count": len(questions),
            "finished_at": _now_iso(),
        })
    except Exception as exc:
        update_generation_job(job_id, {
            "status": "error",
            "message": str(exc),
            "finished_at": _now_iso(),
        })


# ─── Frameworks ───────────────────────────────────────────────────
@router.get("/frameworks")
def api_list_frameworks():
    return get_framework_options()


@router.get("/frameworks/{framework_id}")
def api_get_framework(framework_id: str):
    framework = get_audit_framework(framework_id, include_text=True)
    if not framework:
        raise HTTPException(404, "Framework not found")
    return framework


@router.post("/frameworks")
def api_create_framework(body: AuditFrameworkCreate):
    try:
        return create_audit_framework(body.model_dump(exclude_none=True))
    except ValueError as e:
        raise HTTPException(400, str(e))


@router.post("/frameworks/upload")
async def api_upload_framework(
    name: str = Form(...),
    category: str = Form("custom"),
    source: str = Form(""),
    primary: bool = Form(False),
    enabled: bool = Form(True),
    file: UploadFile = File(...),
):
    suffix = Path(file.filename or "").suffix.lower()
    if suffix not in {".txt", ".md", ".pdf", ".docx", ".xlsx", ".xls"}:
        raise HTTPException(400, f"不支援的檔案格式: {suffix}")

    upload_dir = Path(__file__).resolve().parent.parent / "uploads"
    upload_dir.mkdir(parents=True, exist_ok=True)
    temp_path = upload_dir / f"framework_{uuid.uuid4().hex}{suffix}"
    try:
        with open(temp_path, "wb") as target:
            shutil.copyfileobj(file.file, target)
        if temp_path.stat().st_size > settings.MAX_UPLOAD_SIZE_MB * 1024 * 1024:
            raise HTTPException(400, f"檔案超過 {settings.MAX_UPLOAD_SIZE_MB} MB 限制")
        content = parse_file(str(temp_path))
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(500, f"檔案解析失敗: {e}")
    finally:
        temp_path.unlink(missing_ok=True)

    content = content.strip()
    if not content:
        raise HTTPException(400, "檔案未解析出文字內容")

    framework_id = f"fw_{uuid.uuid4().hex[:12]}"
    try:
        return create_audit_framework({
            "id": framework_id,
            "name": name,
            "category": category,
            "source": source or file.filename or "uploaded file",
            "description": f"由上傳檔案建立：{file.filename}",
            "text": content,
            "compact_text": content[:4000],
            "primary": primary,
            "enabled": enabled,
        })
    except ValueError as e:
        raise HTTPException(400, str(e))


@router.patch("/frameworks/{framework_id}")
def api_update_framework(framework_id: str, body: AuditFrameworkUpdate):
    if not update_audit_framework(framework_id, body.model_dump(exclude_none=True)):
        raise HTTPException(404, "Framework not found")
    return get_audit_framework(framework_id, include_text=True)


@router.delete("/frameworks/{framework_id}")
def api_delete_framework(framework_id: str):
    if not delete_audit_framework(framework_id):
        raise HTTPException(404, "Framework not found")
    return {"ok": True}


@router.get("/controls")
def api_list_controls(framework_id: str | None = None, level: str | None = None):
    return list_audit_controls(framework_id=framework_id, level=level)


@router.post("/controls")
def api_create_control(body: AuditControlCreate):
    try:
        return create_audit_control(body.model_dump())
    except ValueError as e:
        raise HTTPException(400, str(e))


@router.patch("/controls/{control_id}")
def api_update_control(control_id: str, body: AuditControlUpdate):
    if not update_audit_control(control_id, body.model_dump(exclude_none=True)):
        raise HTTPException(404, "Control not found")
    return {"ok": True}


@router.delete("/controls/{control_id}")
def api_delete_control(control_id: str):
    if not delete_audit_control(control_id):
        raise HTTPException(404, "Control not found")
    return {"ok": True}


@router.post("/projects/{project_id}/framework")
def api_set_framework(project_id: str, body: FrameworkSelection):
    if not get_project(project_id):
        raise HTTPException(404, "Project not found")
    update_project(project_id, {
        "frameworks": body.frameworks,
        "responsibility_level": body.responsibility_level,
    })
    return {"ok": True}


# ─── Scope ────────────────────────────────────────────────────────
@router.post("/projects/{project_id}/scope")
def api_set_scope(project_id: str, body: ScopeInput):
    if not get_project(project_id):
        raise HTTPException(404, "Project not found")
    update_project(project_id, {
        "scope": body.scope,
        "context": body.context,
    })
    return {"ok": True}


# ─── Questions ────────────────────────────────────────────────────
@router.post("/projects/{project_id}/questions/generate")
async def api_generate_questions(project_id: str):
    project = get_project(project_id)
    if not project:
        raise HTTPException(404, "Project not found")

    existing = get_questions(project_id)
    generated = await _build_questions_for_project(project, existing_questions=existing)
    target_count = max(1, min(int(project.get("question_count") or len(generated) or 8), 30))
    questions = merge_generated_questions(project_id, generated, target_count)
    return {"questions": questions}


@router.post("/projects/{project_id}/questions/generate/jobs")
async def api_start_question_generation_job(project_id: str):
    if not get_project(project_id):
        raise HTTPException(404, "Project not found")

    active = get_active_generation_job(project_id, "questions")
    if active:
        return active

    job_id = str(uuid.uuid4())
    job = create_generation_job(job_id, project_id, "questions", message="Queued")
    asyncio.create_task(_run_question_job(job_id, project_id))
    return job


@router.get("/question-jobs/{job_id}")
def api_get_question_generation_job(job_id: str):
    job = get_generation_job(job_id)
    if not job:
        raise HTTPException(404, "Job not found")
    return job


@router.get("/projects/{project_id}/questions")
def api_get_questions(project_id: str):
    if not get_project(project_id):
        raise HTTPException(404, "Project not found")
    return get_questions(project_id)


@router.put("/projects/{project_id}/questions")
def api_update_questions(project_id: str, body: QuestionUpdate):
    if not get_project(project_id):
        raise HTTPException(404, "Project not found")
    questions = [q.model_dump() for q in body.questions]
    save_questions(project_id, questions)
    return {"ok": True, "count": len(questions)}


@router.post("/projects/{project_id}/questions")
def api_add_question(project_id: str, body: QuestionCreate):
    if not get_project(project_id):
        raise HTTPException(404, "Project not found")
    return add_question(project_id, body.model_dump())


@router.patch("/questions/{question_id}")
def api_patch_question(question_id: str, body: QuestionPatch):
    """自動儲存：更新單一問題的回覆/狀態/備註"""
    data = body.model_dump(exclude_none=True)
    if not update_question(question_id, data):
        raise HTTPException(404, "Question not found")
    return {"ok": True}


@router.delete("/questions/{question_id}")
def api_delete_question(question_id: str):
    if not delete_question_by_id(question_id):
        raise HTTPException(404, "Question not found")
    return {"ok": True}


# ─── Responses (批次提交) ─────────────────────────────────────────
@router.post("/projects/{project_id}/responses")
def api_submit_responses(project_id: str, body: ResponsesInput):
    if not get_project(project_id):
        raise HTTPException(404, "Project not found")
    for resp in body.responses:
        update_question(resp.question_id, {
            "response_text": resp.response_text,
            "compliance_status": resp.compliance_status,
            "auditor_notes": resp.auditor_notes,
        })
    return {"ok": True}


# ─── Templates ────────────────────────────────────────────────────
@router.get("/templates")
def api_list_templates():
    return [t.model_dump() for t in get_all_templates()]


@router.get("/templates/{template_id}")
def api_get_template(template_id: str):
    t = get_template(template_id)
    if not t:
        raise HTTPException(404, "Template not found")
    return t.model_dump()


# ─── Quick Phrases ────────────────────────────────────────────────
@router.get("/quick-phrases")
def api_get_quick_phrases():
    return get_quick_phrases()
