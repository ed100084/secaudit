"""
LLM 服務 — 支援 OpenRouter / CLIProxyAPI (OpenAI-compatible) 雙後端，SSE 串流
"""
import asyncio
import json
import logging
import re
import threading
import uuid
from typing import AsyncGenerator, List

import httpx
from fastapi.concurrency import run_in_threadpool

from config import settings
from frameworks import get_framework_text, get_framework_names

logger = logging.getLogger(__name__)


# ─── Backend dispatch ──────────────────────────────────────

def _openrouter_headers() -> dict:
    return {
        "Authorization": f"Bearer {settings.OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://secaudit.app",
        "X-Title": "SecAudit",
    }


def _cli_proxy_headers() -> dict:
    h = {"Content-Type": "application/json"}
    if settings.CLI_PROXY_API_KEY:
        h["Authorization"] = f"Bearer {settings.CLI_PROXY_API_KEY}"
    return h


def _build_payload(
    messages: list,
    max_tokens: int = 4096,
    temperature: float = 0.3,
    stream: bool = False,
) -> dict:
    """共用 payload 建構 — OpenRouter / CLIProxyAPI 格式相同"""
    model = (
        settings.OPENROUTER_MODEL
        if settings.LLM_BACKEND == "openrouter"
        else settings.CLI_PROXY_MODEL
    )
    payload = {
        "model": model,
        "messages": messages,
        "max_tokens": max_tokens,
        "temperature": temperature,
        "stream": stream,
    }
    if not stream:
        import random
        payload["seed"] = random.randint(1, 999999)
    return payload


async def _call_llm(messages: list, max_tokens: int = 4096, temperature: float = 0.3) -> str:
    """非串流呼叫 — 依 LLM_BACKEND 路由"""
    payload = _build_payload(messages, max_tokens, temperature)

    if settings.LLM_BACKEND == "openrouter":
        url = "https://openrouter.ai/api/v1/chat/completions"
        headers = _openrouter_headers()
    else:
        url = f"{settings.CLI_PROXY_URL}/chat/completions"
        headers = _cli_proxy_headers()

    async with httpx.AsyncClient(timeout=120) as client:
        for attempt in range(3):
            try:
                resp = await client.post(url, headers=headers, json=payload)
                if resp.status_code in (429, 503) and attempt < 2:
                    wait = 5 * (2 ** attempt)
                    logger.warning(f"LLM backend 限流 (HTTP {resp.status_code})，{wait}s 後重試...")
                    await asyncio.sleep(wait)
                    continue
                resp.raise_for_status()
                data = resp.json()
                return data["choices"][0]["message"]["content"]
            except httpx.HTTPStatusError as e:
                if attempt < 2 and getattr(e.response, "status_code", None) in (429, 503):
                    await asyncio.sleep(5 * (2 ** attempt))
                    continue
                raise

    raise RuntimeError("LLM backend 重試次數已用盡")


async def _stream_llm(messages: list, max_tokens: int = 8192, temperature: float = 0.2) -> AsyncGenerator[str, None]:
    """SSE 串流呼叫 — 依 LLM_BACKEND 路由"""
    payload = _build_payload(messages, max_tokens, temperature, stream=True)

    if settings.LLM_BACKEND == "openrouter":
        url = "https://openrouter.ai/api/v1/chat/completions"
        headers = _openrouter_headers()
    else:
        url = f"{settings.CLI_PROXY_URL}/chat/completions"
        headers = _cli_proxy_headers()

    async with httpx.AsyncClient(timeout=180) as client:
        async with client.stream("POST", url, headers=headers, json=payload) as resp:
            resp.raise_for_status()
            async for line in resp.aiter_lines():
                if not line.startswith("data: "):
                    continue
                data = line[6:]
                if data == "[DONE]":
                    break
                try:
                    chunk_data = json.loads(data)
                    choices = chunk_data.get("choices") or []
                    if not choices:
                        continue
                    delta = choices[0].get("delta") or {}
                    content = delta.get("content", "")
                    if content:
                        yield content
                except json.JSONDecodeError:
                    continue


def _strip_json_fences(text: str) -> str:
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\n?", "", text)
        text = re.sub(r"\n?```$", "", text)
    return text.strip()


def _repair_truncated_json(text: str) -> str:
    """修復被截斷的 JSON"""
    try:
        json.loads(text)
        return text
    except json.JSONDecodeError:
        pass

    stack = []
    in_string = False
    escape_next = False
    candidates = []

    for i, ch in enumerate(text):
        if escape_next:
            escape_next = False
            continue
        if ch == '\\' and in_string:
            escape_next = True
            continue
        if ch == '"':
            in_string = not in_string
            continue
        if in_string:
            continue
        if ch in ('{', '['):
            stack.append(ch)
        elif ch == '}' and stack and stack[-1] == '{':
            stack.pop()
            closing = ''.join(']' if c == '[' else '}' for c in reversed(stack))
            candidates.append((i + 1, closing))
        elif ch == ']' and stack and stack[-1] == '[':
            stack.pop()

    for pos, closing in reversed(candidates):
        candidate = text[:pos] + closing
        try:
            json.loads(candidate)
            logger.warning(f"JSON 已修復：保留 {pos}/{len(text)} chars")
            return candidate
        except json.JSONDecodeError:
            continue

    raise ValueError("JSON 無法修復")


def _extract_json_array(text: str) -> str:
    """Try to extract a JSON array from text that may contain non-JSON preamble/postamble."""
    # Find the first [ and last ]
    start = text.find('[')
    end = text.rfind(']')
    if start >= 0 and end > start:
        candidate = text[start:end + 1]
        try:
            json.loads(candidate)
            return candidate
        except json.JSONDecodeError:
            # Try repair on the extracted portion
            try:
                return _repair_truncated_json(candidate)
            except ValueError:
                pass
    # Try finding a JSON object instead
    start = text.find('{')
    end = text.rfind('}')
    if start >= 0 and end > start:
        candidate = text[start:end + 1]
        # Wrap in array if it's a single object
        try:
            obj = json.loads(candidate)
            if isinstance(obj, dict):
                return json.dumps([obj])
            return candidate
        except json.JSONDecodeError:
            try:
                repaired = _repair_truncated_json(candidate)
                obj = json.loads(repaired)
                if isinstance(obj, dict):
                    return json.dumps([obj])
                return repaired
            except (ValueError, json.JSONDecodeError):
                pass
    raise ValueError("JSON 無法從回應中擷取")


def _build_qa_text(questions: list, responses: list) -> str:
    """將問題與回覆組合成文字供 LLM 分析"""
    resp_map = {}
    for r in responses:
        resp_map[r["question_id"]] = r

    parts = []
    for i, q in enumerate(questions, 1):
        resp = resp_map.get(q["id"], {})
        ans = resp.get("response_text", "[未提供回覆]")
        status = resp.get("compliance_status", "")
        notes = resp.get("auditor_notes", "")

        status_label = {
            "compliant": "✅ 符合",
            "partial": "⚠️ 部分符合",
            "non_compliant": "❌ 不符合",
            "not_applicable": "N/A 不適用",
        }.get(status, "未評估")

        part = (
            f"Q{i} [{q.get('category', '')} | {q.get('source_framework', '')}]"
            f"（依據：{q.get('reference', '')}）\n"
            f"問題：{q['text']}\n"
            f"合規狀態：{status_label}\n"
            f"受稽單位回覆：{ans}"
        )
        if notes:
            part += f"\n稽核員觀察筆記：{notes}"
        parts.append(part)
    return "\n\n---\n\n".join(parts)


async def generate_questions(
    framework_ids: List[str],
    custom_text: str,
    scope: str,
    context: str,
    responsibility_level: str | None,
    target_count: int = 8,
    existing_questions: list | None = None,
) -> list:
    target_count = max(1, min(int(target_count or 8), 30))
    framework_text = get_framework_text(framework_ids, custom_text, compact=True)
    framework_names = ", ".join(get_framework_names(framework_ids))
    if custom_text:
        framework_names += ", 自訂法規文件"

    level_note = ""
    if responsibility_level:
        level_note = f"\n\n受稽單位責任等級：**{responsibility_level} 級**。請依此等級之適用控制要求產生問題。"

    system_prompt = "\n".join([
        "你是一位資深資通安全稽核委員，正在準備現場訪談問題。",
        "你的任務不是逐條照抄法規，而是依稽核範圍挑出最重要、最可能產生風險或缺失的控制重點。",
        "問題要像稽核員現場會問人的話，語氣自然、具體、可回答，不要制式條列盤點。",
        "",
        "【選題原則】",
        "- 每次產生的問題必須與上次不同，若有提供「已產生過的問題」，請完全避開相同主題與角度。",
        "- 只挑高影響、高風險、高機率出問題、跨單位協作、需要證據佐證的重點。",
        "- 多個相近條文或控制措施要合併成一題，不要一條法規問一題。",
        "- 優先涵蓋：權責分工、實際執行、例外處理、紀錄留存、覆核改善、委外/事件/權限/日誌等關鍵風險。",
        "- 若控制措施有高/中/普或 A/B/C 等等級，優先問較高等級與本次範圍最相關者。",
        "",
        "【問法要求】",
        "- 每題用 1 個主問題，加上 2-3 個自然追問即可。",
        "- 要能引導受稽單位說明『平常怎麼做、誰負責、如何確認有做到、出問題怎麼補救』。",
        "- 請用繁體中文，避免官樣文章與過度抽象詞。",
        "- 每題最後可簡短列出希望看到的佐證，但不要變成僵硬清單。",
        "",
        "【輸出規則】",
        "- 僅輸出純 JSON array，不含 markdown 或說明文字。",
        '- 格式：{"id":"<uuid>","text":"問題內容","category":"<稽核領域>","source_framework":"<法規名稱>","reference":"<主要依據或控制重點>","dimension":"interview"}',
        f"- 請產生 exactly {target_count} 題，不要少於或多於這個數量。",
        "- 若控制重點不足，請合併法規要求後從不同稽核角度設計問題，不要逐條照抄法規。",
        "- text 可包含換行，但必須是自然訪談題，不要固定五段模板。",
    ])

    user_message = (
        f"適用法規框架：{framework_names}\n\n"
        f"法規參考內容：\n{framework_text}\n\n"
        f"稽核範圍：{scope}\n\n"
        f"稽核情境/背景：{context}"
        f"{level_note}\n\n"
        f"請先判斷哪些控制重點最值得現場追問，再產生 {target_count} 題自然訪談式稽核問題清單。"
    )

    if existing_questions:
        existing_summary = "\n".join(
            f"- [{q.get('category','')}] {q.get('text','')[:100]}"
            for q in existing_questions[:20]
        )
        user_message += (
            f"\n\n【以下是已經產生過的問題，請勿重複，請從不同角度、不同控制重點出題】\n"
            f"{existing_summary}"
        )

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_message},
    ]

    raw = await _call_llm(messages, max_tokens=max(2048, min(8192, target_count * 700)), temperature=0.7)
    logger.info(f"[generate_questions] raw length={len(raw)}, first 200 chars: {raw[:200]}")
    raw = _strip_json_fences(raw)
    try:
        raw = _repair_truncated_json(raw)
    except ValueError:
        logger.warning("[generate_questions] repair failed, trying extract")
        raw = _extract_json_array(raw)
    questions = json.loads(raw)

    if not isinstance(questions, list):
        raise ValueError("LLM 回傳格式錯誤")

    # 正規化
    normalized = []
    for q in questions:
        if not isinstance(q, dict):
            continue
        text = q.get("text", "")
        if not text:
            continue
        normalized.append({
            "id": q.get("id", str(uuid.uuid4())),
            "text": text,
            "category": q.get("category", "治理與合規"),
            "source_framework": q.get("source_framework", ""),
            "reference": q.get("reference", ""),
            "dimension": q.get("dimension", "interview"),
            "generated_by": "llm",
        })

    if not normalized:
        raise ValueError("LLM 未產生有效問題")

    logger.info(f"[generate_questions] count={len(normalized)}")
    return normalized


async def stream_findings(project: dict, questions: list, responses: list, report_format: str = "iia5c"):
    """SSE 串流產生稽核發現報告"""
    framework_ids = project.get("frameworks", [])
    custom_text = project.get("custom_framework_text", "")
    framework_text = get_framework_text(framework_ids, custom_text)
    framework_names = ", ".join(get_framework_names(framework_ids))
    if custom_text:
        framework_names += ", 自訂法規文件"

    scope = project.get("scope", "")
    responsibility_level = project.get("responsibility_level")
    level_note = f"，受稽單位責任等級：{responsibility_level} 級" if responsibility_level else ""

    qa_text = _build_qa_text(questions, responses)

    if report_format == "gov":
        system_prompt, json_schema = _gov_prompt()
    else:
        system_prompt, json_schema = _iia5c_prompt()

    user_message = (
        f"稽核範圍：{scope}{level_note}\n"
        f"適用法規框架：{framework_names}\n\n"
        f"法規參考內容：\n{framework_text}\n\n"
        f"稽核問答紀錄：\n{qa_text}\n\n"
        f"請產生稽核發現報告。"
    )

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_message},
    ]

    buffer = []

    async for content in _stream_llm(messages, max_tokens=8192, temperature=0.2):
        buffer.append(content)
        yield f"data: {json.dumps({'chunk': content})}\n\n"

    # 嘗試修復截斷的 JSON
    raw = _strip_json_fences("".join(buffer))
    try:
        json.loads(raw)
    except json.JSONDecodeError:
        try:
            repaired = _repair_truncated_json(raw)
            yield f"data: {json.dumps({'repair': repaired})}\n\n"
        except ValueError:
            logger.error("JSON 修復失敗")

    yield "data: [DONE]\n\n"


def _iia5c_prompt():
    json_schema = (
        '{"executive_summary":"string","findings":['
        '{"title":"string","risk_level":"High|Medium|Low",'
        '"regulatory_reference":"string","legal_basis":"string",'
        '"legal_requirement":"string","condition":"string",'
        '"criteria":"string","cause":"string","effect":"string",'
        '"recommendation":"string"}]}'
    )
    system_prompt = "\n".join([
        "你是一位資深資通安全稽核委員，負責撰寫正式稽核發現報告。",
        "根據稽核問答紀錄，對照適用法規框架，識別不符合事項並產生結構化稽核發現。",
        "",
        "輸出規則：",
        "- 僅輸出純 JSON object，不含 markdown",
        f"- 格式：{json_schema}",
        "- executive_summary：繁體中文，2-3 段",
        "- legal_basis：法源依據，具體法條全名",
        "- legal_requirement：應辦事項，法條原文中的強制規定",
        "- condition：現況，稽核發現的具體事實",
        "- criteria：準則，應達到的合規狀態",
        "- cause：原因，造成落差的根本原因",
        "- effect：影響，可能造成的風險或損害",
        "- recommendation：建議改善事項與期限",
        "",
        "- 僅針對有具體證據支持的問題產生發現",
        "- 若回覆顯示已完全符合要求，不產生該項發現",
        "- 特別關注合規狀態標記為「不符合」或「部分符合」的問題",
        "- 發現依風險等級由高至低排序",
    ])
    return system_prompt, json_schema


def _gov_prompt():
    json_schema = (
        '{"executive_summary":"string","findings":['
        '{"finding_type":"法規不符合|待改善缺失|建議缺失",'
        '"title":"string","legal_basis":"string",'
        '"legal_text":"string","finding_description":"string",'
        '"evidence":["string"],"recommendation":"string"}]}'
    )
    system_prompt = "\n".join([
        "你是一位資深資通安全稽核委員，依照台灣政府機關資安稽核格式撰寫報告。",
        "",
        "輸出規則：",
        "- 僅輸出純 JSON object",
        f"- 格式：{json_schema}",
        "- finding_type：法規不符合 / 待改善缺失 / 建議缺失",
        "- legal_text：法條原文，不可改寫",
        "- 特別關注合規狀態標記為「不符合」或「部分符合」的問題",
        "- 發現依類型排序：法規不符合 → 待改善缺失 → 建議缺失",
    ])
    return system_prompt, json_schema
