from typing import List, Optional
from pydantic import BaseModel


# ─── Project ──────────────────────────────────────────────────────
class ProjectCreate(BaseModel):
    name: str = ""
    auditor_name: str = ""
    organization: str = ""


class ProjectUpdate(BaseModel):
    name: Optional[str] = None
    status: Optional[str] = None
    frameworks: Optional[List[str]] = None
    responsibility_level: Optional[str] = None
    scope: Optional[str] = None
    context: Optional[str] = None
    template_id: Optional[str] = None
    question_count: Optional[int] = None
    auditor_name: Optional[str] = None
    organization: Optional[str] = None


# ─── Framework ────────────────────────────────────────────────────
class FrameworkSelection(BaseModel):
    frameworks: List[str]
    responsibility_level: Optional[str] = None


class AuditFrameworkCreate(BaseModel):
    id: Optional[str] = None
    name: str
    name_en: str = ""
    description: str = ""
    category: str = "custom"
    source: str = ""
    text: str = ""
    compact_text: str = ""
    primary: bool = False
    enabled: bool = True


class AuditFrameworkUpdate(BaseModel):
    name: Optional[str] = None
    name_en: Optional[str] = None
    description: Optional[str] = None
    category: Optional[str] = None
    source: Optional[str] = None
    text: Optional[str] = None
    compact_text: Optional[str] = None
    primary: Optional[bool] = None
    enabled: Optional[bool] = None


class AuditControlCreate(BaseModel):
    framework_id: str
    domain: str = ""
    item: str
    level: str = ""
    requirement: str
    reference: str = ""
    source_text: str = ""
    sort_order: int = 0


class AuditControlUpdate(BaseModel):
    domain: Optional[str] = None
    item: Optional[str] = None
    level: Optional[str] = None
    requirement: Optional[str] = None
    reference: Optional[str] = None
    source_text: Optional[str] = None
    sort_order: Optional[int] = None


# ─── Scope ────────────────────────────────────────────────────────
class ScopeInput(BaseModel):
    scope: str
    context: str


# ─── Questions ────────────────────────────────────────────────────
class Question(BaseModel):
    id: str
    text: str
    category: str = ""
    source_framework: str = ""
    reference: str = ""
    dimension: str = "systemic"


class QuestionUpdate(BaseModel):
    questions: List[Question]


class QuestionPatch(BaseModel):
    """單一問題的部分更新 — 用於自動儲存"""
    compliance_status: Optional[str] = None
    response_text: Optional[str] = None
    auditor_notes: Optional[str] = None
    evidence: Optional[List[str]] = None
    text: Optional[str] = None


# ─── Responses ────────────────────────────────────────────────────
class QuestionResponseItem(BaseModel):
    question_id: str
    response_text: str
    compliance_status: Optional[str] = None
    auditor_notes: str = ""


class ResponsesInput(BaseModel):
    responses: List[QuestionResponseItem]


# ─── Findings ─────────────────────────────────────────────────────
class Finding(BaseModel):
    title: str
    risk_level: str
    regulatory_reference: str = ""
    legal_basis: str = ""
    legal_requirement: str = ""
    condition: str = ""
    criteria: str = ""
    cause: str = ""
    effect: str = ""
    recommendation: str = ""


class FindingsReport(BaseModel):
    executive_summary: str
    findings: List[Finding]


class GovFinding(BaseModel):
    finding_type: str
    title: str
    legal_basis: str = ""
    legal_text: str = ""
    finding_description: str = ""
    evidence: List[str] = []
    recommendation: str = ""


class GovFindingsReport(BaseModel):
    executive_summary: str
    findings: List[GovFinding]
