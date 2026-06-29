# SecAudit

資安稽核輔助系統，用於建立稽核專案、選擇法規框架、產生現場稽核問題、記錄受稽單位回答，並產生稽核發現報告。

## 目前狀態

| 項目 | 狀態 |
| --- | --- |
| 目前版本 | `2026.06.29.11` |
| 本機專案目錄 | `D:\workspace\secaudit` |
| Pi 部署主機 | `192.168.88.115` |
| Pi 專案目錄 | `/home/pi/secaudit` |
| 對外服務 URL | `http://192.168.88.115:18000` |
| Container | `secaudit` |
| Runtime | FastAPI + static frontend + SQLite |
| DB | `data/secaudit.db` |
| Auth | `X-API-Key`，由 `.env` 的 `SECAUDIT_API_KEY` 提供 |

## 已完成進度

| 功能 | 狀態 | 說明 |
| --- | --- | --- |
| 專案 CRUD | 已完成 | 可建立、開啟、刪除專案 |
| 法規框架選擇 | 已完成 | 支援內建框架、上傳框架文件、管理控制項 |
| 手機 sidebar | 已修正 | 左側選單可正常開關，避免遮住內容 |
| 框架 checkbox 顯示 | 已修正 | 手機版選取狀態可正常顯示 |
| 稽核問題產生 | 已調整 | 改為 backend job + frontend polling |
| 稽核報告產生 | 已調整 | 改為 backend job + frontend polling |
| 長任務切頁 | 已支援 | 使用者可先切到其他頁面，之後再回來看 |
| job 狀態持久化 | 已完成 | `generation_jobs` table 保存 question/report job 狀態 |
| 專案列表 job badge | 已完成 | 所有專案頁可看到問題/報告產生中、完成、失敗 |
| 重新整理後恢復進度 | 已完成 | 開啟專案後會從 DB 還原 running job 並恢復 polling |
| 問題數設定 | 已完成 | 專案設定頁可設定產出問題數，範圍 `1-30` |
| rule-based 產題 | 已移除 | 不再用固定模板補題，產題完全依 LLM 回傳 |
| Pi 部署 | 已完成 | 版本 `2026.06.29.11` 已部署並確認 container healthy |

## 目前產題流程

```text
使用者設定問題數
→ 儲存 project.question_count
→ POST /api/projects/{project_id}/questions/generate/jobs
→ backend 建立 generation_jobs 記錄
→ background task 呼叫 LLM
→ save_questions 寫入 SQLite
→ 更新 generation_jobs 狀態
→ frontend polling /api/question-jobs/{job_id}
```

重點：

- 不再使用 `question_generator.generate_rule_questions()` 補題。
- LLM 若只回傳少量有效題目，系統會保留實際有效題目，不再自動補模板題。
- LLM 失敗時，job 狀態會變成 `error`，前端顯示失敗訊息。

## 目前報告流程

```text
使用者按產生報告
→ POST /api/projects/{project_id}/findings/jobs
→ backend 建立 generation_jobs 記錄
→ background task 收集 LLM stream 結果
→ save_findings 寫入 SQLite
→ 更新 generation_jobs 狀態
→ frontend polling /api/finding-jobs/{job_id}
```

## 主要 API

| API | 用途 |
| --- | --- |
| `GET /api/version` | 查版本 |
| `GET /api/projects` | 專案列表，含 `jobs` summary |
| `GET /api/projects/{project_id}` | 單一專案，含 `jobs` summary |
| `GET /api/projects/{project_id}/jobs` | 單一專案最新 question/report job 狀態 |
| `POST /api/projects/{project_id}/questions/generate/jobs` | 啟動稽核問題產生 job |
| `GET /api/question-jobs/{job_id}` | 查問題產生 job 狀態 |
| `POST /api/projects/{project_id}/findings/jobs?format=iia5c` | 啟動報告產生 job |
| `GET /api/finding-jobs/{job_id}` | 查報告產生 job 狀態 |

## 部署與驗證

Pi 部署目錄：

```powershell
ssh pi@192.168.88.115 "cd /home/pi/secaudit && docker compose up -d --build secaudit"
```

版本檢查：

```powershell
ssh pi@192.168.88.115 "curl -fsS http://127.0.0.1:18000/api/version && echo"
```

Container 狀態：

```powershell
ssh pi@192.168.88.115 "docker ps --filter name=secaudit --format 'table {{.Names}}\t{{.Ports}}\t{{.Status}}'"
```

Logs：

```powershell
ssh pi@192.168.88.115 "docker logs --tail 50 secaudit"
```

## 目前限制與風險

| 項目 | 說明 |
| --- | --- |
| background task | 仍使用 FastAPI process 內的 `asyncio.create_task`，不是 Celery/RQ 這類外部 queue |
| container 重啟 | running job 的 DB 狀態會保留，但實際 background task 會中斷；後續應補啟動時標記 interrupted |
| LLM 題數控制 | prompt 要求 exact 題數，但模型仍可能少回或多回；目前不做 rule-based 補題 |
| 多使用者協作 | 尚未做完整 user/session 權限模型，目前依 API key 保護 |
| 憑證 | `.env` 不應提交，README 不記錄 API key 值 |

## 建議下一步

| 優先順序 | 工作 |
| --- | --- |
| 短期 | container 啟動時把過久未更新的 `running` job 標為 `interrupted` |
| 短期 | job badge 加上開始時間/耗時 tooltip |
| 中期 | 針對 LLM 題數不足加入「LLM retry」，但仍不回到 rule-based |
| 中期 | 報告與問題 job 加取消功能 |
| 長期 | 將 background job 改成正式 queue worker，提高重啟與併發可靠性 |
