from typing import List, Dict

from .csma_core import CSMA_CORE_CONTEXT
from .csma_classification import CSMA_CLASSIFICATION_CONTEXT
from .csma_incident import CSMA_INCIDENT_CONTEXT
from .csma_sharing import CSMA_SHARING_CONTEXT
from .iso27001 import ISO27001_CONTEXT
from .iso27701 import ISO27701_CONTEXT

FRAMEWORK_REGISTRY: Dict[str, dict] = {
    "csma_core": {
        "id": "csma_core",
        "name": "資通安全管理法",
        "name_en": "Cybersecurity Management Act",
        "description": "資通安全管理法及施行細則，包含 CISO 設置、維護計畫、委外管理等核心要求",
        "primary": True,
        "text": CSMA_CORE_CONTEXT,
    },
    "csma_classification": {
        "id": "csma_classification",
        "name": "責任等級分級辦法",
        "name_en": "Responsibility Level Classification",
        "description": "A-E 五級分類，各等級管理、技術、人員控制要求",
        "primary": True,
        "text": CSMA_CLASSIFICATION_CONTEXT,
    },
    "csma_incident": {
        "id": "csma_incident",
        "name": "事件通報及應變辦法",
        "name_en": "Incident Notification & Response",
        "description": "1 小時通報 SLA、事件分級、應變程序、演練要求",
        "primary": True,
        "text": CSMA_INCIDENT_CONTEXT,
    },
    "csma_sharing": {
        "id": "csma_sharing",
        "name": "情資分享辦法",
        "name_en": "Cybersecurity Information Sharing",
        "description": "威脅情資分享義務、保密規定、情資運用要求",
        "primary": False,
        "text": CSMA_SHARING_CONTEXT,
    },
    "iso27001": {
        "id": "iso27001",
        "name": "ISO 27001:2022",
        "name_en": "ISO/IEC 27001:2022",
        "description": "資訊安全管理系統國際標準，Annex A 93 項控制措施",
        "primary": False,
        "text": ISO27001_CONTEXT,
    },
    "iso27701": {
        "id": "iso27701",
        "name": "ISO 27701:2025",
        "name_en": "ISO/IEC 27701:2025",
        "description": "隱私資訊管理系統，PII 控制者/處理者控制措施",
        "primary": False,
        "text": ISO27701_CONTEXT,
    },
}

DEFAULT_FRAMEWORKS = ["csma_core", "csma_classification", "csma_incident"]

COMPACT_TEXTS: Dict[str, str] = {
    "csma_core": """資通安全管理法 重點條文：
第10條 資通安全維護計畫（政策、風險評估、防護措施、事件應變、委外管理、人員訓練、稽核）
第11條 資通安全長（CISO）設置
第12條 資通安全專責人員配置
第15條 委外管理（契約資安條款、廠商能力驗證、分包商管控）
第16條 資通安全演練
第17條 資通安全稽核配合義務""",

    "csma_classification": """責任等級分級辦法 重點：
A級：ISO 27001必要、每年2次稽核、專責人員≥2人、SOC監控、滲透測試
B級：ISO 27001建議、每年2次稽核、專責人員≥1人、定期弱點掃描
C級：每年1次稽核、兼任可、基礎防護、訓練≥3小時/年
稽核三大面向：管理面（政策/組織/計畫）、技術面（防護/監控/測試）、人員面（訓練/認知）""",

    "csma_incident": """事件通報及應變辦法 重點：
事件分級：1-4級，1-2級知悉後1小時內通報，3級8小時，4級72小時
通報內容：機關名稱、發生/知悉時間、事件類型、等級評估、影響範圍、應變措施
應變程序：偵測→通報→遏制→證據保全（不得銷毀）→根因分析→復原→改善
演練要求：A/B級每年參與主管機關演練，機關自辦每年至少1次""",

    "csma_sharing": """資通安全情資分享辦法 重點：
應分享：惡意程式樣本、攻擊來源IP/網域、IoC、漏洞利用資訊
時機：知悉影響他機關威脅時即時分享、事件後分享摘要
保密：不得揭露他方營業秘密、個資、法律限制資訊""",

    "iso27001": """ISO/IEC 27001:2022 主要控制領域（Annex A）：
A.5 組織控制：政策、角色責任、職務分離、資產管理、存取控制、供應商管理
A.6 人員控制：背景查核、聘僱條款、教育訓練、懲戒
A.7 實體控制：門禁、設備安置、安全銷毀
A.8 技術控制：端點設備、特殊權限、弱點管理、備份、日誌、網路安全、加密""",

    "iso27701": """ISO/IEC 27701:2025 隱私控制重點：
PII控制者：合法處理基礎、當事人同意、資料主體權利、目的限制、資料最小化
PII處理者：依指示處理、保密義務、外洩通報
共通：隱私影響評估(PIA)、Privacy by Design、跨境傳輸控制""",
}


def get_framework_text(framework_ids: List[str], custom_text: str = "", compact: bool = False) -> str:
    parts = []
    dynamic = _get_dynamic_frameworks(framework_ids)
    for fid in framework_ids:
        if fid in dynamic:
            framework = dynamic[fid]
            text = framework.get("compact_text") if compact and framework.get("compact_text") else framework.get("text", "")
            parts.append(text)
        elif fid in FRAMEWORK_REGISTRY:
            text = COMPACT_TEXTS.get(fid, FRAMEWORK_REGISTRY[fid]["text"]) if compact else FRAMEWORK_REGISTRY[fid]["text"]
            parts.append(text)
    if custom_text:
        limit = 2000 if compact else 50000
        parts.append(f"自訂法規/標準：\n{custom_text[:limit]}")
    return "\n\n".join(parts)


def get_framework_names(framework_ids: List[str]) -> List[str]:
    dynamic = _get_dynamic_frameworks(framework_ids, include_text=False)
    names = []
    for fid in framework_ids:
        if fid in dynamic:
            names.append(dynamic[fid].get("name", fid))
        elif fid in FRAMEWORK_REGISTRY:
            names.append(FRAMEWORK_REGISTRY[fid]["name"])
    return names


def get_framework_options() -> List[dict]:
    try:
        from db import list_audit_frameworks
        return list_audit_frameworks(enabled_only=True, include_text=False)
    except Exception:
        return [
            {k: v for k, v in fw.items() if k != "text"}
            for fw in FRAMEWORK_REGISTRY.values()
        ]


def _get_dynamic_frameworks(framework_ids: List[str], include_text: bool = True) -> Dict[str, dict]:
    if not framework_ids:
        return {}
    try:
        from db import get_audit_framework
        result = {}
        for fid in framework_ids:
            framework = get_audit_framework(fid, include_text=include_text)
            if framework and framework.get("enabled", True):
                result[fid] = framework
        return result
    except Exception:
        return {}
