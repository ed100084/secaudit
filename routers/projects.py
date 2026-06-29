"""
專案 CRUD API
"""
from fastapi import APIRouter, HTTPException

from db import (
    create_project, get_project, list_projects, update_project, delete_project,
    list_project_generation_jobs,
)
from models import ProjectCreate, ProjectUpdate

router = APIRouter(tags=["projects"])


@router.post("/projects")
def api_create_project(body: ProjectCreate):
    project = create_project(
        name=body.name,
        auditor_name=body.auditor_name,
        organization=body.organization,
    )
    return project


@router.get("/projects")
def api_list_projects(auditor: str | None = None):
    return list_projects(auditor_name=auditor)


@router.get("/projects/{project_id}")
def api_get_project(project_id: str):
    project = get_project(project_id)
    if not project:
        raise HTTPException(404, "Project not found")
    return project


@router.get("/projects/{project_id}/jobs")
def api_get_project_jobs(project_id: str):
    if not get_project(project_id):
        raise HTTPException(404, "Project not found")
    return list_project_generation_jobs(project_id)


@router.patch("/projects/{project_id}")
def api_update_project(project_id: str, body: ProjectUpdate):
    data = body.model_dump(exclude_none=True)
    if not update_project(project_id, data):
        raise HTTPException(404, "Project not found")
    return get_project(project_id)


@router.delete("/projects/{project_id}")
def api_delete_project(project_id: str):
    if not delete_project(project_id):
        raise HTTPException(404, "Project not found")
    return {"ok": True}
