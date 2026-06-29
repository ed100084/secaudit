import uuid

from frameworks import FRAMEWORK_REGISTRY
from frameworks import get_framework_names
from question_bank import QUESTION_BANK


DEFAULT_TARGET_COUNT = 10


def generate_rule_questions(
    framework_ids: list[str],
    scope: str,
    context: str = "",
    responsibility_level: str | None = None,
    custom_text: str = "",
    target_count: int = DEFAULT_TARGET_COUNT,
) -> list[dict]:
    selected_ids = _enabled_framework_ids(framework_ids)
    selected = _select_control_items(selected_ids, target_count)
    remaining = max(target_count - len(selected), 0)
    if remaining:
        selected.extend(_select_bank_items(selected_ids, bool(custom_text), remaining))

    questions = []
    for item in selected[:target_count]:
        questions.append(_build_question(item, selected_ids, scope, context, responsibility_level))
    return questions


def _enabled_framework_ids(framework_ids: list[str]) -> list[str]:
    if not framework_ids:
        return []
    try:
        from db import get_audit_framework
        return [fid for fid in framework_ids if get_audit_framework(fid, include_text=False)]
    except Exception:
        return [fid for fid in framework_ids if fid in FRAMEWORK_REGISTRY]


def _select_control_items(framework_ids: list[str], target_count: int) -> list[dict]:
    if not framework_ids:
        return []
    try:
        from db import list_audit_controls
        controls = []
        for fid in framework_ids:
            controls.extend(list_audit_controls(framework_id=fid))
    except Exception:
        return []

    items = []
    seen = set()
    for control in controls:
        key = control.get("id") or f"{control.get('framework_id')}:{control.get('item')}"
        if key in seen:
            continue
        seen.add(key)
        items.append(_control_to_bank_item(control))
        if len(items) >= target_count:
            break
    return items


def _control_to_bank_item(control: dict) -> dict:
    level = control.get("level", "")
    level_note = f"（適用等級：{level}）" if level else ""
    requirement = control.get("requirement", "")
    reference = control.get("reference", "") or control.get("source_text", "")[:80]
    return {
        "id": f"control_{control.get('id')}",
        "framework_ids": [control.get("framework_id", "")],
        "category": control.get("domain", "控制措施") or "控制措施",
        "reference": reference,
        "title": f"{control.get('item', '控制措施')} 的落實情形{level_note}",
        "prompts": [
            f"請說明此控制要求如何轉換為內部制度、程序或系統設定：{_shorten(requirement, 120)}",
            "請說明實際執行流程、負責角色、頻率與留存紀錄。",
            "請提供最近一次執行、覆核、檢核或改善追蹤結果。",
            "例外情境：若此控制未完全落實或無法提供佐證，如何評估風險並改善？",
        ],
        "evidence": ["控制程序", "執行紀錄", "覆核紀錄", "改善追蹤"],
    }


def _select_bank_items(framework_ids: list[str], has_custom_text: bool, target_count: int) -> list[dict]:
    selected = [
        item
        for item in QUESTION_BANK
        if not framework_ids or set(item["framework_ids"]) & set(framework_ids)
    ]
    if has_custom_text:
        selected.insert(0, _custom_reference_item())

    if not selected:
        selected = list(QUESTION_BANK)

    result = []
    seen = set()
    for item in selected + QUESTION_BANK:
        if item["id"] in seen:
            continue
        result.append(item)
        seen.add(item["id"])
        if len(result) >= target_count:
            break
    return result


def _build_question(
    item: dict,
    framework_ids: list[str],
    scope: str,
    context: str,
    responsibility_level: str | None,
) -> dict:
    prompts = list(item["prompts"])
    if responsibility_level:
        prompts.insert(
            1,
            f"請說明此控制如何符合責任等級 {responsibility_level} 級的適用要求。",
        )

    context_note = ""
    if context:
        context_note = f"\n稽核背景：{_shorten(context, 90)}"

    text = "\n".join([
        f"【{item['category']}】{item['title']}",
        f"稽核範圍：{_shorten(scope, 90)}{context_note}",
        *[f"({idx}) {prompt}" for idx, prompt in enumerate(prompts, 1)],
        "★ 請提供：" + "、".join(item["evidence"]),
    ])

    return {
        "id": str(uuid.uuid4()),
        "text": text,
        "category": item["category"],
        "source_framework": _source_framework(item, framework_ids),
        "reference": item["reference"],
        "dimension": "systemic",
        "generated_by": "rules",
    }


def _source_framework(item: dict, framework_ids: list[str]) -> str:
    for fid in item["framework_ids"]:
        if fid in framework_ids:
            names = get_framework_names([fid])
            if names:
                return names[0]
    if not item["framework_ids"]:
        return "自訂文件"
    first = item["framework_ids"][0]
    return FRAMEWORK_REGISTRY.get(first, {}).get("name", "內建題庫")


def _shorten(value: str, limit: int) -> str:
    value = " ".join((value or "").split())
    if len(value) <= limit:
        return value
    return value[: limit - 1] + "…"


def _custom_reference_item() -> dict:
    return {
        "id": "custom_reference",
        "framework_ids": [],
        "category": "治理與合規",
        "reference": "自訂文件",
        "title": "自訂法規或內部文件要求的適用性",
        "prompts": [
            "請說明自訂文件中哪些條文或要求適用於本次稽核範圍。",
            "請說明受稽單位如何將文件要求轉換為內部程序、控制或紀錄。",
            "請提供最近一次依該文件執行檢核或改善追蹤的結果。",
            "例外情境：若文件要求與現行作業不一致，如何評估差距並提出改善計畫？",
        ],
        "evidence": ["自訂文件", "適用性分析", "內部程序", "檢核或改善紀錄"],
    }
