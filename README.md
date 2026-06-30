# SecAudit

資安稽核輔助系統，用於建立稽核專案、選擇法規框架、產生現場稽核問題、記錄受稽單位回答，並產生稽核發現報告。

## 目前狀態

| 項目 | 狀態 |
| --- | --- |
| 目前版本 | `2026.06.30.2` |
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
| job badge 耗時 | 已完成 | 專案列表顯示問題/報告 job 耗時，hover 可看開始、更新、完成時間與訊息 |
| 重新整理後恢復進度 | 已完成 | 開啟專案後會從 DB 還原 running job 並恢復 polling |
| 問題數設定 | 已完成 | 專案設定頁可設定產出問題數，範圍 `1-30` |
| rule-based 產題 | 已移除 | 不再用固定模板補題，產題完全依 LLM 回傳 |
| 增加題數保留回答 | 已完成 | 調高問題數時只追加新題，不覆蓋已填答案 |
| 報告切頁保留 | 已完成 | 切離報告頁再回來會自動從 DB 載入最近報告 |
| 預設政府格式 | 已完成 | 稽核報告預設使用政府機關格式 |
| LLM stream 容錯 | 已修正 | 空 choices/content 自動重試，不再導致 job crash |
| Qwen reasoning model 相容 | 已修正 | 對 Qwen 類模型加 `/no_think` 並提高 token floor，避免只回 reasoning_content 導致 content 空值 |
| LLM 題目 ID 去信任 | 已修正 | 追加 LLM 題目時由 backend 重新產生 UUID，避免模型回傳重複 id 撞 DB |
| framework ingestion v1 | 已完成 | 上傳文件會產生 Markdown preview、diagnostics，並抽取應辦事項為 controls |
| LLM JSON 解析強化 | 已完成 | 三層 fallback：strip fences → repair truncated → extract array |
| 問題多樣性 | 已完成 | 既有題目回饋進 prompt、temperature 0.7、random seed |
| 題數不足處理 | 已修正 | 會依缺少題數最多 retry 3 次，未達目標不再誤標完成 |
| 題數不足提示 | 已完成 | Record view 顯示已產出/目標題數，並提供重新產生與手動新增 |
| 問題 CRUD | 已完成 | 每題可刪除、編輯問題文字、手動新增問題 |
| 報告歷史選擇 | 已完成 | 可切換不同次產出的報告 |
| 報告編輯/刪除 | 已完成 | 摘要、每項 finding 可 inline 編輯，可刪除單項或整份報告 |
| 框架 checkbox 保留 | 已修正 | 切頁後勾選狀態不再消失 |
| 框架儲存同步 | 已修正 | 產生問題前會從目前 checkbox 重新讀取，避免前端 state 與畫面不同步 |
| 穩定化 gate | 已建立 | `smoke_check.ps1` 檢查語法、版本、critical hooks、static browser wiring，可加 Pi/API smoke |
| frontend 模組切割 | 進行中 | 已抽出 `static/js/ui.js` 與 `static/js/projects.js`，降低 `main.js` global state 面積 |
| 殘屍 job 清理 | 已完成 | container 啟動時自動標記中斷的 running job |
| Git 版本控制 | 已完成 | GitHub: ed100084/secaudit |
| Pi 部署 | 已完成 | 版本 `2026.06.30.2` 已部署並確認 container running |

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
- 調高問題數重新產生時，既有問題與回答會保留，只追加新題到目標數。
- 產題時會將既有題目回饋進 LLM prompt，避免產出重複問題。
- 若 LLM 一次產出不足，會按缺少題數最多 retry 3 次。
- 若 retry 後仍未達目標，job 會標記 `error`，並保留已成功產出的部分問題。
- LLM 失敗時，job 狀態會變成 `error`，前端顯示失敗訊息。
- 不需要的問題可直接刪除，也可手動新增或編輯問題文字。

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
| `POST /api/projects/{project_id}/questions` | 手動新增單題 |
| `DELETE /api/questions/{question_id}` | 刪除單題 |
| `POST /api/projects/{project_id}/findings/jobs?format=gov` | 啟動報告產生 job（預設政府格式） |
| `GET /api/finding-jobs/{job_id}` | 查報告產生 job 狀態 |
| `GET /api/findings/{finding_id}` | 取得單份報告 |
| `PATCH /api/findings/{finding_id}` | 更新報告內容 |
| `DELETE /api/findings/{finding_id}` | 刪除報告 |

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
| container 重啟 | 啟動時自動標記中斷的 running job，但不會自動重試 |
| LLM 題數控制 | prompt 要求 exact 題數，但模型仍可能少回或多回；目前不做 rule-based 補題 |
| 多使用者協作 | 尚未做完整 user/session 權限模型，目前依 API key 保護 |
| 憑證 | `.env` 不應提交，README 不記錄 API key 值 |

## 建議下一步

先依 [STABILIZATION_PLAN.md](STABILIZATION_PLAN.md) 做穩定化，不再直接追加新功能。

| 優先順序 | 工作 |
| --- | --- |
| 短期 | 視需要把 static browser wiring checks 升級成真正 browser click automation |
| 短期 | 針對 LLM 題數不足加入「LLM retry」 |
| 中期 | 報告與問題 job 加取消功能 |
| 中期 | 報告匯出 PDF/Word |
| 長期 | 將 background job 改成正式 queue worker，提高重啟與併發可靠性 |
