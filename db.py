"""
SQLite 持久化層 — 專案導向設計
所有稽核資料自動持久化，不因瀏覽器關閉而遺失。
"""
import json
import sqlite3
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, List

DB_PATH = Path(__file__).parent / "data" / "secaudit.db"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


@contextmanager
def _db():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    _ensure_schema(conn)
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def _ensure_schema(conn: sqlite3.Connection):
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS projects (
            id                    TEXT PRIMARY KEY,
            name                  TEXT NOT NULL DEFAULT '',
            status                TEXT NOT NULL DEFAULT 'setup',
            frameworks            TEXT NOT NULL DEFAULT '[]',
            responsibility_level  TEXT,
            scope                 TEXT NOT NULL DEFAULT '',
            context               TEXT NOT NULL DEFAULT '',
            template_id           TEXT,
            question_count        INTEGER NOT NULL DEFAULT 8,
            auditor_name          TEXT NOT NULL DEFAULT '',
            organization          TEXT NOT NULL DEFAULT '',
            custom_framework_text TEXT NOT NULL DEFAULT '',
            created_at            TEXT NOT NULL,
            updated_at            TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS questions (
            id                TEXT PRIMARY KEY,
            project_id        TEXT NOT NULL,
            sort_order        INTEGER NOT NULL DEFAULT 0,
            text              TEXT NOT NULL,
            category          TEXT NOT NULL DEFAULT '',
            source_framework  TEXT NOT NULL DEFAULT '',
            reference         TEXT NOT NULL DEFAULT '',
            dimension         TEXT NOT NULL DEFAULT 'systemic',
            compliance_status TEXT,
            response_text     TEXT NOT NULL DEFAULT '',
            auditor_notes     TEXT NOT NULL DEFAULT '',
            evidence          TEXT NOT NULL DEFAULT '[]',
            updated_at        TEXT NOT NULL,
            FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS findings (
            id             TEXT PRIMARY KEY,
            project_id     TEXT NOT NULL,
            report_format  TEXT NOT NULL DEFAULT 'iia5c',
            report_data    TEXT,
            created_at     TEXT NOT NULL,
            FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS generation_jobs (
            job_id       TEXT PRIMARY KEY,
            project_id   TEXT NOT NULL,
            job_type     TEXT NOT NULL,
            format       TEXT,
            status       TEXT NOT NULL DEFAULT 'running',
            message      TEXT NOT NULL DEFAULT '',
            result_count INTEGER NOT NULL DEFAULT 0,
            created_at   TEXT NOT NULL,
            updated_at   TEXT NOT NULL,
            finished_at  TEXT,
            FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS quick_phrases (
            id         TEXT PRIMARY KEY,
            category   TEXT NOT NULL DEFAULT 'general',
            text       TEXT NOT NULL,
            sort_order INTEGER NOT NULL DEFAULT 0
        );

        CREATE TABLE IF NOT EXISTS audit_frameworks (
            id           TEXT PRIMARY KEY,
            name         TEXT NOT NULL,
            name_en      TEXT NOT NULL DEFAULT '',
            description  TEXT NOT NULL DEFAULT '',
            category     TEXT NOT NULL DEFAULT 'custom',
            source       TEXT NOT NULL DEFAULT '',
            text         TEXT NOT NULL DEFAULT '',
            compact_text TEXT NOT NULL DEFAULT '',
            primary_flag INTEGER NOT NULL DEFAULT 0,
            enabled      INTEGER NOT NULL DEFAULT 1,
            created_at   TEXT NOT NULL,
            updated_at   TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS audit_controls (
            id           TEXT PRIMARY KEY,
            framework_id TEXT NOT NULL,
            domain       TEXT NOT NULL DEFAULT '',
            item         TEXT NOT NULL,
            level        TEXT NOT NULL DEFAULT '',
            requirement  TEXT NOT NULL,
            reference    TEXT NOT NULL DEFAULT '',
            source_text  TEXT NOT NULL DEFAULT '',
            sort_order   INTEGER NOT NULL DEFAULT 0,
            created_at   TEXT NOT NULL,
            updated_at   TEXT NOT NULL,
            FOREIGN KEY (framework_id) REFERENCES audit_frameworks(id) ON DELETE CASCADE
        );

        CREATE INDEX IF NOT EXISTS idx_questions_project ON questions(project_id);
        CREATE INDEX IF NOT EXISTS idx_findings_project ON findings(project_id);
        CREATE INDEX IF NOT EXISTS idx_generation_jobs_project ON generation_jobs(project_id, job_type, updated_at);
        CREATE INDEX IF NOT EXISTS idx_audit_controls_framework ON audit_controls(framework_id);
    """)
    _ensure_project_columns(conn)
    _seed_quick_phrases(conn)
    _seed_audit_frameworks(conn)


def _ensure_project_columns(conn: sqlite3.Connection):
    columns = {
        row[1]
        for row in conn.execute("PRAGMA table_info(projects)").fetchall()
    }
    if "question_count" not in columns:
        conn.execute("ALTER TABLE projects ADD COLUMN question_count INTEGER NOT NULL DEFAULT 8")


def _seed_audit_frameworks(conn: sqlite3.Connection):
    """Seed built-in frameworks into the dynamic registry without overwriting edits."""
    count = conn.execute("SELECT COUNT(*) FROM audit_frameworks").fetchone()[0]
    if count > 0:
        return

    from frameworks import FRAMEWORK_REGISTRY, COMPACT_TEXTS

    now = _now()
    rows = []
    for fid, fw in FRAMEWORK_REGISTRY.items():
        rows.append((
            fid,
            fw.get("name", fid),
            fw.get("name_en", ""),
            fw.get("description", ""),
            "built-in",
            fw.get("source", ""),
            fw.get("text", ""),
            COMPACT_TEXTS.get(fid, fw.get("text", "")),
            1 if fw.get("primary") else 0,
            1,
            now,
            now,
        ))
    conn.executemany(
        """INSERT INTO audit_frameworks
           (id, name, name_en, description, category, source, text, compact_text,
            primary_flag, enabled, created_at, updated_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        rows,
    )


def _seed_quick_phrases(conn: sqlite3.Connection):
    """預設快捷短語，只在表為空時寫入"""
    count = conn.execute("SELECT COUNT(*) FROM quick_phrases").fetchone()[0]
    if count > 0:
        return
    phrases = [
        ("response", "受稽單位表示：", 1),
        ("response", "經查，", 2),
        ("response", "受稽單位已提供相關文件佐證。", 3),
        ("response", "受稽單位表示目前尚無相關機制。", 4),
        ("response", "受稽單位表示正在規劃中，預計於 _____ 前完成。", 5),
        ("observation", "未能提供相關佐證文件。", 10),
        ("observation", "經檢視文件，發現", 11),
        ("observation", "經系統實機查核，確認", 12),
        ("observation", "與前次稽核結果比較，", 13),
        ("observation", "依現場訪談結果，", 14),
        ("compliance", "已符合法規要求。", 20),
        ("compliance", "部分符合，但仍有改善空間。", 21),
        ("compliance", "未符合法規要求，建議限期改善。", 22),
        ("compliance", "不適用於本次稽核範圍。", 23),
    ]
    conn.executemany(
        "INSERT INTO quick_phrases (id, category, text, sort_order) VALUES (?, ?, ?, ?)",
        [(str(uuid.uuid4()), cat, text, order) for cat, text, order in phrases],
    )


# ═══════════════════════════════════════════════════════
# Projects
# ═══════════════════════════════════════════════════════

def create_project(name: str = "", auditor_name: str = "", organization: str = "") -> dict:
    project_id = str(uuid.uuid4())
    now = _now()
    project = {
        "id": project_id,
        "name": name or f"稽核專案 {now[:10]}",
        "status": "setup",
        "frameworks": [],
        "responsibility_level": None,
        "scope": "",
        "context": "",
        "template_id": None,
        "question_count": 8,
        "auditor_name": auditor_name,
        "organization": organization,
        "custom_framework_text": "",
        "created_at": now,
        "updated_at": now,
    }
    with _db() as conn:
        conn.execute(
            """INSERT INTO projects (id, name, status, frameworks, responsibility_level,
               scope, context, template_id, question_count, auditor_name, organization,
               custom_framework_text, created_at, updated_at)
               VALUES (:id, :name, :status, :frameworks, :responsibility_level,
               :scope, :context, :template_id, :question_count, :auditor_name, :organization,
               :custom_framework_text, :created_at, :updated_at)""",
            {**project, "frameworks": json.dumps(project["frameworks"])},
        )
    return project


def get_project(project_id: str) -> Optional[dict]:
    with _db() as conn:
        row = conn.execute("SELECT * FROM projects WHERE id = ?", (project_id,)).fetchone()
        jobs = _latest_jobs_for_projects(conn, [project_id])
    if not row:
        return None
    d = dict(row)
    d["frameworks"] = json.loads(d["frameworks"])
    d["jobs"] = jobs.get(project_id, {})
    return d


def list_projects(auditor_name: Optional[str] = None) -> List[dict]:
    with _db() as conn:
        if auditor_name:
            rows = conn.execute(
                "SELECT id, name, status, scope, auditor_name, organization, created_at, updated_at "
                "FROM projects WHERE auditor_name = ? ORDER BY updated_at DESC",
                (auditor_name,),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT id, name, status, scope, auditor_name, organization, created_at, updated_at "
                "FROM projects ORDER BY updated_at DESC"
            ).fetchall()
        result = [dict(r) for r in rows]
        jobs = _latest_jobs_for_projects(conn, [p["id"] for p in result])
    for project in result:
        project["jobs"] = jobs.get(project["id"], {})
    return result


def update_project(project_id: str, data: dict) -> bool:
    project = get_project(project_id)
    if not project:
        return False
    project.update(data)
    project["updated_at"] = _now()
    with _db() as conn:
        conn.execute(
            """UPDATE projects SET name=?, status=?, frameworks=?, responsibility_level=?,
               scope=?, context=?, template_id=?, question_count=?, auditor_name=?, organization=?,
               custom_framework_text=?, updated_at=?
               WHERE id=?""",
            (
                project["name"], project["status"],
                json.dumps(project.get("frameworks", [])),
                project.get("responsibility_level"),
                project.get("scope", ""),
                project.get("context", ""),
                project.get("template_id"),
                project.get("question_count", 8),
                project.get("auditor_name", ""),
                project.get("organization", ""),
                project.get("custom_framework_text", ""),
                project["updated_at"],
                project_id,
            ),
        )
    return True


def delete_project(project_id: str) -> bool:
    with _db() as conn:
        cursor = conn.execute("DELETE FROM projects WHERE id = ?", (project_id,))
        return cursor.rowcount > 0


def _job_from_row(row: sqlite3.Row) -> dict:
    job = dict(row)
    if job.get("job_type") == "questions":
        job["question_count"] = job.get("result_count", 0)
    if job.get("job_type") == "report":
        job["finding_count"] = job.get("result_count", 0)
    return job


def _latest_jobs_for_projects(conn: sqlite3.Connection, project_ids: list[str]) -> dict:
    if not project_ids:
        return {}
    placeholders = ",".join("?" for _ in project_ids)
    rows = conn.execute(
        f"""SELECT * FROM generation_jobs
            WHERE project_id IN ({placeholders})
            ORDER BY updated_at DESC, created_at DESC""",
        project_ids,
    ).fetchall()

    result: dict[str, dict] = {}
    for row in rows:
        job = _job_from_row(row)
        project_jobs = result.setdefault(job["project_id"], {})
        key = "questions" if job["job_type"] == "questions" else "report"
        if key not in project_jobs:
            project_jobs[key] = job
    return result


def create_generation_job(
    job_id: str,
    project_id: str,
    job_type: str,
    message: str = "Queued",
    format: str | None = None,
) -> dict:
    now = _now()
    job = {
        "job_id": job_id,
        "project_id": project_id,
        "job_type": job_type,
        "format": format,
        "status": "running",
        "message": message,
        "result_count": 0,
        "created_at": now,
        "updated_at": now,
        "finished_at": None,
    }
    with _db() as conn:
        conn.execute(
            """INSERT INTO generation_jobs
               (job_id, project_id, job_type, format, status, message, result_count,
                created_at, updated_at, finished_at)
               VALUES (:job_id, :project_id, :job_type, :format, :status, :message,
                :result_count, :created_at, :updated_at, :finished_at)""",
            job,
        )
    return _job_from_row(job)


def update_generation_job(job_id: str, data: dict) -> bool:
    job = get_generation_job(job_id)
    if not job:
        return False
    current = {
        "status": job.get("status", "running"),
        "message": job.get("message", ""),
        "result_count": job.get("result_count", 0),
        "finished_at": job.get("finished_at"),
    }
    if "question_count" in data:
        data["result_count"] = data.pop("question_count")
    if "finding_count" in data:
        data["result_count"] = data.pop("finding_count")
    current.update(data)
    current["updated_at"] = _now()
    with _db() as conn:
        conn.execute(
            """UPDATE generation_jobs
               SET status=?, message=?, result_count=?, updated_at=?, finished_at=?
               WHERE job_id=?""",
            (
                current["status"],
                current["message"],
                current.get("result_count", 0),
                current["updated_at"],
                current.get("finished_at"),
                job_id,
            ),
        )
    return True


def get_generation_job(job_id: str) -> Optional[dict]:
    with _db() as conn:
        row = conn.execute("SELECT * FROM generation_jobs WHERE job_id = ?", (job_id,)).fetchone()
    return _job_from_row(row) if row else None


def get_active_generation_job(project_id: str, job_type: str, format: str | None = None) -> Optional[dict]:
    sql = """SELECT * FROM generation_jobs
             WHERE project_id = ? AND job_type = ? AND status = 'running'"""
    params: list = [project_id, job_type]
    if format is not None:
        sql += " AND format = ?"
        params.append(format)
    sql += " ORDER BY created_at DESC LIMIT 1"
    with _db() as conn:
        row = conn.execute(sql, params).fetchone()
    return _job_from_row(row) if row else None


def list_project_generation_jobs(project_id: str) -> dict:
    with _db() as conn:
        return _latest_jobs_for_projects(conn, [project_id]).get(project_id, {})


# ═══════════════════════════════════════════════════════
# Audit Frameworks / Controls
# ═══════════════════════════════════════════════════════

def _framework_from_row(row: sqlite3.Row, include_text: bool = False) -> dict:
    d = dict(row)
    d["primary"] = bool(d.pop("primary_flag", 0))
    d["enabled"] = bool(d.get("enabled", 1))
    if not include_text:
        d.pop("text", None)
        d.pop("compact_text", None)
    return d


def list_audit_frameworks(enabled_only: bool = True, include_text: bool = False) -> List[dict]:
    sql = "SELECT * FROM audit_frameworks"
    params = []
    if enabled_only:
        sql += " WHERE enabled = 1"
    sql += " ORDER BY primary_flag DESC, category, name"
    with _db() as conn:
        rows = conn.execute(sql, params).fetchall()
    return [_framework_from_row(r, include_text=include_text) for r in rows]


def get_audit_framework(framework_id: str, include_text: bool = True) -> Optional[dict]:
    with _db() as conn:
        row = conn.execute("SELECT * FROM audit_frameworks WHERE id = ?", (framework_id,)).fetchone()
    if not row:
        return None
    return _framework_from_row(row, include_text=include_text)


def create_audit_framework(data: dict) -> dict:
    now = _now()
    framework_id = data.get("id") or str(uuid.uuid4())
    framework = {
        "id": framework_id,
        "name": data.get("name", "").strip(),
        "name_en": data.get("name_en", "").strip(),
        "description": data.get("description", "").strip(),
        "category": data.get("category", "custom").strip() or "custom",
        "source": data.get("source", "").strip(),
        "text": data.get("text", "").strip(),
        "compact_text": data.get("compact_text", "").strip(),
        "primary_flag": 1 if data.get("primary") else 0,
        "enabled": 1 if data.get("enabled", True) else 0,
        "created_at": now,
        "updated_at": now,
    }
    if not framework["name"]:
        raise ValueError("Framework name is required")
    with _db() as conn:
        conn.execute(
            """INSERT INTO audit_frameworks
               (id, name, name_en, description, category, source, text, compact_text,
                primary_flag, enabled, created_at, updated_at)
               VALUES (:id, :name, :name_en, :description, :category, :source,
                :text, :compact_text, :primary_flag, :enabled, :created_at, :updated_at)""",
            framework,
        )
    return get_audit_framework(framework_id, include_text=True)


def update_audit_framework(framework_id: str, data: dict) -> bool:
    framework = get_audit_framework(framework_id, include_text=True)
    if not framework:
        return False
    framework.update(data)
    framework["updated_at"] = _now()
    with _db() as conn:
        conn.execute(
            """UPDATE audit_frameworks SET name=?, name_en=?, description=?, category=?,
               source=?, text=?, compact_text=?, primary_flag=?, enabled=?, updated_at=?
               WHERE id=?""",
            (
                framework.get("name", ""),
                framework.get("name_en", ""),
                framework.get("description", ""),
                framework.get("category", "custom"),
                framework.get("source", ""),
                framework.get("text", ""),
                framework.get("compact_text", ""),
                1 if framework.get("primary") else 0,
                1 if framework.get("enabled", True) else 0,
                framework["updated_at"],
                framework_id,
            ),
        )
    return True


def delete_audit_framework(framework_id: str) -> bool:
    with _db() as conn:
        cursor = conn.execute("DELETE FROM audit_frameworks WHERE id = ?", (framework_id,))
        return cursor.rowcount > 0


def list_audit_controls(framework_id: Optional[str] = None, level: Optional[str] = None) -> List[dict]:
    sql = "SELECT * FROM audit_controls"
    clauses = []
    params = []
    if framework_id:
        clauses.append("framework_id = ?")
        params.append(framework_id)
    if level:
        clauses.append("level = ?")
        params.append(level)
    if clauses:
        sql += " WHERE " + " AND ".join(clauses)
    sql += " ORDER BY framework_id, domain, sort_order, item"
    with _db() as conn:
        rows = conn.execute(sql, params).fetchall()
    return [dict(r) for r in rows]


def create_audit_control(data: dict) -> dict:
    now = _now()
    control_id = str(uuid.uuid4())
    control = {
        "id": control_id,
        "framework_id": data.get("framework_id", ""),
        "domain": data.get("domain", "").strip(),
        "item": data.get("item", "").strip(),
        "level": data.get("level", "").strip(),
        "requirement": data.get("requirement", "").strip(),
        "reference": data.get("reference", "").strip(),
        "source_text": data.get("source_text", "").strip(),
        "sort_order": data.get("sort_order", 0),
        "created_at": now,
        "updated_at": now,
    }
    if not control["framework_id"] or not control["item"] or not control["requirement"]:
        raise ValueError("framework_id, item and requirement are required")
    with _db() as conn:
        conn.execute(
            """INSERT INTO audit_controls
               (id, framework_id, domain, item, level, requirement, reference,
                source_text, sort_order, created_at, updated_at)
               VALUES (:id, :framework_id, :domain, :item, :level, :requirement,
                :reference, :source_text, :sort_order, :created_at, :updated_at)""",
            control,
        )
        row = conn.execute("SELECT * FROM audit_controls WHERE id = ?", (control_id,)).fetchone()
    return dict(row)


def update_audit_control(control_id: str, data: dict) -> bool:
    with _db() as conn:
        row = conn.execute("SELECT * FROM audit_controls WHERE id = ?", (control_id,)).fetchone()
        if not row:
            return False
        current = dict(row)
        current.update(data)
        current["updated_at"] = _now()
        conn.execute(
            """UPDATE audit_controls SET domain=?, item=?, level=?, requirement=?,
               reference=?, source_text=?, sort_order=?, updated_at=? WHERE id=?""",
            (
                current.get("domain", ""),
                current.get("item", ""),
                current.get("level", ""),
                current.get("requirement", ""),
                current.get("reference", ""),
                current.get("source_text", ""),
                current.get("sort_order", 0),
                current["updated_at"],
                control_id,
            ),
        )
    return True


def delete_audit_control(control_id: str) -> bool:
    with _db() as conn:
        cursor = conn.execute("DELETE FROM audit_controls WHERE id = ?", (control_id,))
        return cursor.rowcount > 0


# ═══════════════════════════════════════════════════════
# Questions
# ═══════════════════════════════════════════════════════

def save_questions(project_id: str, questions: list):
    now = _now()
    with _db() as conn:
        conn.execute("DELETE FROM questions WHERE project_id = ?", (project_id,))
        for i, q in enumerate(questions):
            conn.execute(
                """INSERT INTO questions (id, project_id, sort_order, text, category,
                   source_framework, reference, dimension, compliance_status,
                   response_text, auditor_notes, evidence, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    q.get("id", str(uuid.uuid4())),
                    project_id, i,
                    q.get("text", ""),
                    q.get("category", ""),
                    q.get("source_framework", ""),
                    q.get("reference", ""),
                    q.get("dimension", "systemic"),
                    q.get("compliance_status"),
                    q.get("response_text", ""),
                    q.get("auditor_notes", ""),
                    json.dumps(q.get("evidence", [])),
                    now,
                ),
            )
        conn.execute(
            "UPDATE projects SET status = 'in_progress', updated_at = ? WHERE id = ?",
            (now, project_id),
        )


def get_questions(project_id: str) -> list:
    with _db() as conn:
        rows = conn.execute(
            "SELECT * FROM questions WHERE project_id = ? ORDER BY sort_order",
            (project_id,),
        ).fetchall()
    result = []
    for r in rows:
        d = dict(r)
        d["evidence"] = json.loads(d["evidence"])
        result.append(d)
    return result


def update_question(question_id: str, data: dict) -> bool:
    """更新單一問題的回覆、狀態、備註等 — 支援自動儲存"""
    now = _now()
    with _db() as conn:
        row = conn.execute("SELECT * FROM questions WHERE id = ?", (question_id,)).fetchone()
        if not row:
            return False
        current = dict(row)
        current.update(data)
        conn.execute(
            """UPDATE questions SET compliance_status=?, response_text=?,
               auditor_notes=?, evidence=?, text=?, updated_at=?
               WHERE id=?""",
            (
                current.get("compliance_status"),
                current.get("response_text", ""),
                current.get("auditor_notes", ""),
                json.dumps(current.get("evidence", [])) if isinstance(current.get("evidence"), list) else current.get("evidence", "[]"),
                current.get("text", ""),
                now,
                question_id,
            ),
        )
        conn.execute(
            "UPDATE projects SET updated_at = ? WHERE id = ?",
            (now, current["project_id"]),
        )
    return True


# ═══════════════════════════════════════════════════════
# Findings
# ═══════════════════════════════════════════════════════

def save_findings(project_id: str, report_format: str, report_data: dict) -> str:
    finding_id = str(uuid.uuid4())
    now = _now()
    with _db() as conn:
        conn.execute(
            "INSERT INTO findings (id, project_id, report_format, report_data, created_at) VALUES (?, ?, ?, ?, ?)",
            (finding_id, project_id, report_format, json.dumps(report_data, ensure_ascii=False), now),
        )
        conn.execute(
            "UPDATE projects SET status = 'completed', updated_at = ? WHERE id = ?",
            (now, project_id),
        )
    return finding_id


def get_findings(project_id: str) -> list:
    with _db() as conn:
        rows = conn.execute(
            "SELECT * FROM findings WHERE project_id = ? ORDER BY created_at DESC",
            (project_id,),
        ).fetchall()
    result = []
    for r in rows:
        d = dict(r)
        if d["report_data"]:
            d["report_data"] = json.loads(d["report_data"])
        result.append(d)
    return result


# ═══════════════════════════════════════════════════════
# Quick Phrases
# ═══════════════════════════════════════════════════════

def get_quick_phrases() -> list:
    with _db() as conn:
        rows = conn.execute("SELECT * FROM quick_phrases ORDER BY sort_order").fetchall()
    return [dict(r) for r in rows]
