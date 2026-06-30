import { S } from './state.js';
import { api, getApiKey, getAuditorName, setAuditorName, openSSE, uploadApi } from './api.js';
import { $, $$, closeSidebar, esc, hideLoading, isMobileViewport, showLoading, showToast, toggleSidebar } from './ui.js?v=2026.06.30.1';
import { createProjectsModule } from './projects.js?v=2026.06.30.1';

// ─── Helpers ─────────────────────────────────────────────
const Projects = createProjectsModule({
  S,
  $,
  api,
  esc,
  showToast,
  showLoading,
  hideLoading,
  getAuditorName,
  navigate,
  loadFrameworks,
  loadTemplates,
  fillSetupForm,
  restoreProjectJobs,
});

const { loadProjects, createNewProject, openProject, deleteProject } = Projects;
// ─── Navigation ──────────────────────────────────────────
const VIEW_META = {
  dashboard: { title: '總覽', subtitle: '稽核專案管理' },
  setup:     { title: '專案設定', subtitle: '選擇框架與設定範圍' },
  record:    { title: '現場記錄', subtitle: '記錄稽核問答' },
  report:    { title: '稽核報告', subtitle: '產生與檢視報告' },
  projects:  { title: '所有專案', subtitle: '管理所有稽核專案' },
  frameworks:{ title: '框架管理', subtitle: '維護稽核知識庫與控制措施' },
};

function navigate(view) {
  if (isMobileViewport()) closeSidebar();
  S.currentView = view;
  $$('.view').forEach(v => v.classList.remove('active'));
  const el = $(`#view-${view}`);
  if (el) el.classList.add('active');
  $$('.nav-item').forEach(n => {
    n.classList.toggle('active', n.dataset.view === view);
  });
  const meta = VIEW_META[view] || {};
  $('#view-title').textContent = meta.title || '';
  $('#view-subtitle').textContent = meta.subtitle || '';
  syncGenerationStatusTimer();

  if (view === 'dashboard') refreshDashboard();
  if (view === 'projects') loadProjects();
  if (view === 'frameworks') loadFrameworkAdmin();
  if (view === 'record') renderRecordView();
  if (view === 'report') renderReportView();
  if (view === 'setup') {
    loadFrameworks();
    if (S.templates.length === 0) loadTemplates();
  }
}

// ─── Dashboard ───────────────────────────────────────────
async function refreshDashboard() {
  if (!S.projectId) {
    $('#dashboard-empty').classList.remove('hidden');
    $('#dashboard-content').classList.add('hidden');
    return;
  }
  $('#dashboard-empty').classList.add('hidden');
  $('#dashboard-content').classList.remove('hidden');
  try {
    S.project = await api('GET', `/projects/${S.projectId}`);
    S.questions = await api('GET', `/projects/${S.projectId}/questions`);
  } catch (_) {}
  renderDashboardStats();
}

function renderDashboardStats() {
  const qs = S.questions;
  const total = qs.length;
  const answered = qs.filter(q => q.response_text).length;
  const compliant = qs.filter(q => q.compliance_status === 'compliant').length;
  const nonComp = qs.filter(q => q.compliance_status === 'non_compliant').length;
  const partial = qs.filter(q => q.compliance_status === 'partial').length;

  $('#dashboard-stats').innerHTML = [
    { v: total, l: '稽核問題', c: 'var(--accent)' },
    { v: answered, l: '已回覆', c: 'var(--info)' },
    { v: compliant, l: '符合', c: 'var(--success)' },
    { v: partial, l: '部分符合', c: 'var(--warning)' },
    { v: nonComp, l: '不符合', c: 'var(--danger)' },
  ].map(s => `<div class="stat-card fade-in"><div class="stat-value" style="color:${s.c}">${s.v}</div><div class="stat-label">${s.l}</div></div>`).join('');
}

function jobStartedAt(job) {
  const started = Date.parse(job.created_at || job.updated_at || '');
  return Number.isFinite(started) ? started : Date.now();
}

function restoreProjectJobs(jobs) {
  const questionJob = jobs.questions;
  if (questionJob?.status === 'running') {
    clearQuestionPollTimer();
    S.questions = [];
    S.questionGeneration = {
      projectId: S.projectId,
      jobId: questionJob.job_id,
      status: 'running',
      message: questionJob.message || 'AI 正在背景產生稽核問題，可先切到其他頁面',
      startedAt: jobStartedAt(questionJob),
      promise: null,
    };
    $('#nav-record-badge').textContent = '…';
    pollQuestionGeneration(questionJob.job_id, S.projectId);
    S.questionPollTimer = setInterval(() => pollQuestionGeneration(questionJob.job_id, S.projectId), 2000);
  } else if (questionJob?.status === 'error') {
    S.questionGeneration = {
      projectId: S.projectId,
      jobId: questionJob.job_id,
      status: 'error',
      message: questionJob.message || '產生問題失敗',
      startedAt: jobStartedAt(questionJob),
      questionCount: questionJob.question_count || questionJob.result_count || 0,
      targetCount: S.project?.question_count || 0,
      promise: null,
    };
  }

  const reportJob = jobs.report;
  if (reportJob?.status === 'running') {
    clearReportPollTimer();
    S.reportGeneration = {
      projectId: S.projectId,
      jobId: reportJob.job_id,
      status: 'running',
      format: reportJob.format || S.reportFormat,
      message: reportJob.message || 'AI 正在背景產生稽核報告，可先切到其他頁面',
      startedAt: jobStartedAt(reportJob),
      promise: null,
    };
    pollReportGeneration(reportJob.job_id, S.projectId, S.reportGeneration.format);
    S.reportPollTimer = setInterval(() => pollReportGeneration(reportJob.job_id, S.projectId, S.reportGeneration.format), 2000);
  }
}

function fillSetupForm() {
  if (!S.project) return;
  const p = S.project;
  $('#project-name').value = p.name || '';
  $('#project-org').value = p.organization || '';
  $('#resp-level').value = p.responsibility_level || '';
  $('#question-count').value = p.question_count || 8;
  $('#scope-input').value = p.scope || '';
  $('#context-input').value = p.context || '';
  const templateSelect = $('#template-select');
  if (templateSelect) templateSelect.value = p.template_id || '';
  S.frameworks = p.frameworks?.length ? [...p.frameworks] : [];
  renderFrameworkChecks(S.frameworks);
}

// ─── Audit Templates ─────────────────────────────────────
async function loadTemplates() {
  try {
    S.templates = await api('GET', '/templates');
    renderTemplateOptions();
  } catch (e) { showToast('載入範本失敗'); }
}

function renderTemplateOptions() {
  const el = $('#template-select');
  if (!el) return;
  const selected = S.project?.template_id || el.value || '';
  const groups = S.templates.reduce((acc, t) => {
    const category = t.category || '其他';
    if (!acc[category]) acc[category] = [];
    acc[category].push(t);
    return acc;
  }, {});

  el.innerHTML = '<option value="">-- 自行輸入 --</option>' + Object.entries(groups).map(([category, templates]) => `
    <optgroup label="${esc(category)}">
      ${templates.map(t => `<option value="${esc(t.id)}">${esc(t.name)}</option>`).join('')}
    </optgroup>`).join('');
  el.value = selected;
}

function applyTemplate(templateId) {
  if (!templateId) return;
  const template = S.templates.find(t => t.id === templateId);
  if (!template) return;

  $('#scope-input').value = template.scope || '';
  $('#context-input').value = template.context || '';

  if (template.suggested_frameworks?.length) {
    S.frameworks = [...template.suggested_frameworks];
    renderFrameworkChecks(S.frameworks);
  }

  const respLevel = $('#resp-level');
  if (respLevel && template.responsibility_levels?.length === 1) {
    respLevel.value = template.responsibility_levels[0];
  }

  showToast('已套用稽核情境範本', 'success');
}

// ─── Frameworks ──────────────────────────────────────────
async function loadFrameworks() {
  try {
    const fws = await api('GET', '/frameworks');
    if (S.project?.frameworks?.length) {
      S.frameworks = [...S.project.frameworks];
    } else if (!S.frameworks.length) {
      S.frameworks = fws.filter(fw => fw.primary).map(fw => fw.id);
    }
    const el = $('#framework-list');
    el.innerHTML = fws.map(fw => {
      const checked = S.frameworks.includes(fw.id);
      return `
      <label class="framework-card">
        <input type="checkbox" class="sr-only" value="${fw.id}" ${checked ? 'checked' : ''} onchange="onFrameworkToggle('${fw.id}', this.checked)">
        <div class="framework-body">
          <div class="fw-checkbox" aria-hidden="true"></div>
          <div style="flex:1">
            <div><span class="fw-name">${esc(fw.name)}</span><span class="fw-name-en">${esc(fw.name_en || '')}</span>${fw.primary ? '<span class="fw-badge">推薦</span>' : ''}</div>
            <div class="fw-desc">${esc(fw.description || '')}</div>
          </div>
        </div>
      </label>`;
    }).join('');
  } catch (e) { showToast('載入框架失敗'); }
}

function renderFrameworkChecks(selected) {
  $$('#framework-list input[type=checkbox]').forEach(cb => {
    cb.checked = selected.includes(cb.value);
  });
}

function onFrameworkToggle(id, checked) {
  if (checked && !S.frameworks.includes(id)) S.frameworks.push(id);
  else S.frameworks = S.frameworks.filter(f => f !== id);
}

function syncFrameworksFromDom() {
  const boxes = [...$$('#framework-list input[type=checkbox]')];
  if (boxes.length) {
    S.frameworks = boxes.filter(cb => cb.checked).map(cb => cb.value);
  }
  return [...S.frameworks];
}

// ─── Framework Admin ────────────────────────────────────
async function loadFrameworkAdmin() {
  try {
    S.frameworkAdmin = await api('GET', '/frameworks');
    renderFrameworkAdminList();
    if (!S.selectedFrameworkId && S.frameworkAdmin.length) selectFrameworkAdmin(S.frameworkAdmin[0].id);
  } catch (e) { showToast('載入框架失敗：' + e.message); }
}

function renderFrameworkAdminList() {
  const el = $('#framework-admin-list');
  if (!el) return;
  if (!S.frameworkAdmin.length) {
    el.innerHTML = '<div class="empty-state"><div class="empty-state-title">尚無框架</div></div>';
    return;
  }
  el.innerHTML = S.frameworkAdmin.map(fw => `
    <div class="admin-row">
      <div class="flex items-center justify-between gap-12">
        <div class="flex-1">
          <div style="font-weight:600">${esc(fw.name)} ${fw.primary ? '<span class="fw-badge">推薦</span>' : ''} ${fw.enabled ? '' : '<span class="fw-badge">停用</span>'}</div>
          <div class="text-xs text-muted mt-8">${esc(fw.id)} · ${esc(fw.category || '')} · ${esc(fw.description || '')}</div>
        </div>
        <div class="flex gap-8">
          <button class="btn btn-ghost btn-sm" onclick="selectFrameworkAdmin('${esc(fw.id)}')">編輯</button>
          <button class="btn btn-ghost btn-sm" onclick="deleteFrameworkAdmin('${esc(fw.id)}')">刪除</button>
        </div>
      </div>
    </div>`).join('');
}

async function selectFrameworkAdmin(id) {
  try {
    const fw = await api('GET', `/frameworks/${id}`);
    S.selectedFrameworkId = id;
    $('#framework-editor-title').textContent = `編輯框架：${fw.name}`;
    $('#fw-edit-id').value = fw.id || '';
    $('#fw-edit-id').disabled = true;
    $('#fw-edit-name').value = fw.name || '';
    $('#fw-edit-name-en').value = fw.name_en || '';
    $('#fw-edit-description').value = fw.description || '';
    $('#fw-edit-category').value = fw.category || 'custom';
    $('#fw-edit-source').value = fw.source || '';
    $('#fw-edit-primary').checked = !!fw.primary;
    $('#fw-edit-enabled').checked = fw.enabled !== false;
    $('#fw-edit-compact').value = fw.compact_text || '';
    $('#fw-edit-text').value = fw.text || '';
    $('#control-framework-label').textContent = fw.name;
    await loadControls(id);
  } catch (e) { showToast('載入框架內容失敗：' + e.message); }
}

function newFrameworkForm() {
  S.selectedFrameworkId = null;
  $('#framework-editor-title').textContent = '新增框架';
  ['fw-edit-id','fw-edit-name','fw-edit-name-en','fw-edit-description','fw-edit-source','fw-edit-compact','fw-edit-text'].forEach(id => { const el = $('#' + id); if (el) el.value = ''; });
  $('#fw-edit-id').disabled = false;
  $('#fw-edit-category').value = 'custom';
  $('#fw-edit-primary').checked = false;
  $('#fw-edit-enabled').checked = true;
  $('#control-framework-label').textContent = '請先選擇框架';
  S.controls = [];
  renderControls();
}

async function saveFramework() {
  const payload = {
    name: $('#fw-edit-name').value.trim(),
    name_en: $('#fw-edit-name-en').value.trim(),
    description: $('#fw-edit-description').value.trim(),
    category: $('#fw-edit-category').value,
    source: $('#fw-edit-source').value.trim(),
    text: $('#fw-edit-text').value.trim(),
    compact_text: $('#fw-edit-compact').value.trim(),
    primary: $('#fw-edit-primary').checked,
    enabled: $('#fw-edit-enabled').checked,
  };
  if (!payload.name) { showToast('請輸入框架名稱'); return; }

  try {
    const id = $('#fw-edit-id').value.trim();
    const saved = S.selectedFrameworkId
      ? await api('PATCH', `/frameworks/${S.selectedFrameworkId}`, payload)
      : await api('POST', '/frameworks', { ...payload, id: id || undefined });
    showToast('框架已儲存', 'success');
    S.selectedFrameworkId = saved.id;
    await loadFrameworkAdmin();
    await loadFrameworks();
  } catch (e) { showToast('儲存框架失敗：' + e.message); }
}

async function deleteFrameworkAdmin(id) {
  if (!confirm('確定刪除此框架與其控制措施？')) return;
  try {
    await api('DELETE', `/frameworks/${id}`);
    if (S.selectedFrameworkId === id) newFrameworkForm();
    await loadFrameworkAdmin();
    await loadFrameworks();
  } catch (e) { showToast('刪除框架失敗：' + e.message); }
}

async function uploadFrameworkSource() {
  const file = $('#fw-upload-file')?.files?.[0];
  const name = $('#fw-upload-name').value.trim();
  if (!name) { showToast('請輸入框架名稱'); return; }
  if (!file) { showToast('請選擇檔案'); return; }

  const formData = new FormData();
  formData.append('name', name);
  formData.append('category', $('#fw-upload-category').value);
  formData.append('source', $('#fw-upload-source').value.trim());
  formData.append('file', file);

  showLoading('解析法條原文...');
  try {
    const saved = await uploadApi('/frameworks/upload', formData);
    showToast('法條原文已建立為框架', 'success');
    renderFrameworkIngestionResult(saved.ingestion);
    $('#fw-upload-name').value = '';
    $('#fw-upload-source').value = '';
    $('#fw-upload-file').value = '';
    S.selectedFrameworkId = saved.id;
    await loadFrameworkAdmin();
    await loadFrameworks();
    await selectFrameworkAdmin(saved.id);
  } catch (e) { showToast('上傳失敗：' + e.message); }
  finally { hideLoading(); }
}

function renderFrameworkIngestionResult(ingestion) {
  const el = $('#framework-ingestion-result');
  if (!el) return;
  if (!ingestion) {
    el.classList.add('hidden');
    el.innerHTML = '';
    return;
  }
  const d = ingestion.diagnostics || {};
  const stats = [
    d.parser ? `Parser: ${d.parser}` : '',
    d.page_count ? `頁數: ${d.page_count}` : '',
    d.pages_with_text !== undefined ? `有文字頁: ${d.pages_with_text}` : '',
    d.table_count ? `表格: ${d.table_count}` : '',
    d.sheet_count ? `工作表: ${d.sheet_count}` : '',
    d.char_count !== undefined ? `字數: ${d.char_count}` : '',
    `控制措施: ${ingestion.control_count || 0}`,
  ].filter(Boolean).join(' · ');
  el.classList.remove('hidden');
  el.innerHTML = `
    <div class="alert ${ingestion.suspected_scanned ? 'alert-warning' : ''}" style="align-items:flex-start">
      <div class="flex-1">
        <div class="alert-title">${ingestion.suspected_scanned ? '疑似掃描 PDF，建議改用 OCR' : '框架解析完成'}</div>
        <div class="alert-desc">${esc(stats)}</div>
        <details class="mt-8">
          <summary class="text-xs text-muted" style="cursor:pointer">查看解析預覽</summary>
          <pre class="parse-preview">${esc(ingestion.preview || '')}</pre>
        </details>
      </div>
    </div>
  `;
}

async function loadControls(frameworkId) {
  S.controls = await api('GET', `/controls?framework_id=${encodeURIComponent(frameworkId)}`);
  renderControls();
}

function renderControls() {
  const el = $('#control-list');
  if (!el) return;
  if (!S.controls.length) {
    el.innerHTML = '<div class="text-sm text-muted">尚無控制措施</div>';
    return;
  }
  el.innerHTML = S.controls.map(c => `
    <div class="admin-row">
      <div class="flex items-start justify-between gap-12">
        <div class="flex-1">
          <div style="font-weight:600">${esc(c.domain || '未分類')} / ${esc(c.item)} ${c.level ? `<span class="fw-badge">${esc(c.level)}</span>` : ''}</div>
          <div class="text-xs text-muted mt-8">${esc(c.reference || '')}</div>
          <div class="text-sm mt-8" style="white-space:pre-wrap">${esc(c.requirement || '')}</div>
        </div>
        <button class="btn btn-ghost btn-sm" onclick="deleteControlAdmin('${esc(c.id)}')">刪除</button>
      </div>
    </div>`).join('');
}

async function saveControl() {
  if (!S.selectedFrameworkId) { showToast('請先選擇框架'); return; }
  const payload = {
    framework_id: S.selectedFrameworkId,
    domain: $('#control-domain').value.trim(),
    item: $('#control-item').value.trim(),
    level: $('#control-level').value.trim(),
    reference: $('#control-reference').value.trim(),
    requirement: $('#control-requirement').value.trim(),
  };
  if (!payload.item || !payload.requirement) { showToast('請輸入控制項與要求內容'); return; }
  try {
    await api('POST', '/controls', payload);
    ['control-domain','control-item','control-level','control-reference','control-requirement'].forEach(id => $('#' + id).value = '');
    await loadControls(S.selectedFrameworkId);
    showToast('控制措施已新增', 'success');
  } catch (e) { showToast('新增控制措施失敗：' + e.message); }
}

async function deleteControlAdmin(id) {
  if (!confirm('確定刪除此控制措施？')) return;
  try {
    await api('DELETE', `/controls/${id}`);
    await loadControls(S.selectedFrameworkId);
  } catch (e) { showToast('刪除控制措施失敗：' + e.message); }
}

// ─── Start Audit ─────────────────────────────────────────
async function startAudit() {
  const selectedFrameworks = syncFrameworksFromDom();
  const name = $('#project-name').value.trim();
  const org = $('#project-org').value.trim();
  const scope = $('#scope-input').value.trim();
  const context = $('#context-input').value.trim();
  const respLevel = $('#resp-level').value;
  const questionCount = Math.max(1, Math.min(Number.parseInt($('#question-count').value, 10) || 8, 30));

  if (!scope) { showToast('請輸入稽核範圍'); return; }
  if (!context) { showToast('請輸入稽核情境'); return; }
  if (selectedFrameworks.length === 0) { showToast('請至少選擇一個法規框架'); return; }

  showLoading('儲存專案設定...');
  try {
    if (!S.projectId) {
      const p = await api('POST', '/projects', { name: name || `稽核 ${new Date().toLocaleDateString('zh-TW')}`, auditor_name: getAuditorName(), organization: org });
      S.projectId = p.id;
      S.project = p;
    } else {
      await api('PATCH', `/projects/${S.projectId}`, { name, organization: org, question_count: questionCount });
    }

    await api('POST', `/projects/${S.projectId}/framework`, { frameworks: selectedFrameworks, responsibility_level: respLevel || null });
    await api('PATCH', `/projects/${S.projectId}`, { template_id: $('#template-select')?.value || null, question_count: questionCount });
    await api('POST', `/projects/${S.projectId}/scope`, { scope, context });

    S.project = await api('GET', `/projects/${S.projectId}`);
    $('#project-name-display').textContent = S.project.name;
    hideLoading();
    await startQuestionGeneration(S.projectId, { throwOnError: true });
    navigate('record');
    showToast('已開始在背景產生稽核問題，可先切到其他頁面', 'success');
  } catch (e) {
    if (S.projectId && S.questionGeneration.status === 'error') navigate('record');
    showToast('產生問題失敗：' + e.message);
  }
  finally { hideLoading(); }
}

function startQuestionGeneration(projectId, options = {}) {
  if (S.questionGeneration.status === 'running' && S.questionGeneration.projectId === projectId) {
    return S.questionGeneration.promise || Promise.resolve(S.questionGeneration);
  }

  clearQuestionPollTimer();
  S.questions = [];
  S.questionGeneration = {
    projectId,
    jobId: null,
    status: 'running',
    message: 'AI 正在背景產生稽核問題，可先切到其他頁面',
    startedAt: Date.now(),
    promise: null,
  };
  $('#nav-record-badge').textContent = '…';

  const promise = api('POST', `/projects/${projectId}/questions/generate/jobs`)
    .then((job) => {
      S.questionGeneration = {
        ...S.questionGeneration,
        jobId: job.job_id,
        message: job.message || S.questionGeneration.message,
      };
      pollQuestionGeneration(job.job_id, projectId);
      S.questionPollTimer = setInterval(() => pollQuestionGeneration(job.job_id, projectId), 2000);
    })
    .catch((e) => {
      S.questionGeneration = {
        ...S.questionGeneration,
        status: 'error',
        message: `啟動產生任務失敗：${e.message}`,
        promise: null,
      };
      $('#nav-record-badge').textContent = '!';
      if (S.currentView === 'record') renderRecordView();
      showToast(S.questionGeneration.message);
      if (options.throwOnError) throw e;
      return null;
    });

  S.questionGeneration.promise = promise;
  return promise;
}

function clearQuestionPollTimer() {
  if (S.questionPollTimer) {
    clearInterval(S.questionPollTimer);
    S.questionPollTimer = null;
  }
}

async function pollQuestionGeneration(jobId, projectId) {
  if (!jobId) return;
  try {
    const job = await api('GET', `/question-jobs/${jobId}`);
    if (job.status === 'running') {
      S.questionGeneration = {
        ...S.questionGeneration,
        jobId,
        projectId,
        status: 'running',
        message: job.message || 'AI 正在背景產生稽核問題，可先切到其他頁面',
      };
      if (S.currentView === 'record') renderRecordEmptyState();
      return;
    }

    clearQuestionPollTimer();
    if (job.status === 'done') {
      S.questions = await api('GET', `/projects/${projectId}/questions`);
      if (S.projectId === projectId) {
        S.project = await api('GET', `/projects/${projectId}`);
        $('#project-name-display').textContent = S.project.name;
      }
      S.questionGeneration = {
        ...S.questionGeneration,
        jobId,
        status: 'done',
        message: `已產生 ${S.questions.length} 題稽核問題`,
        promise: null,
      };
      $('#nav-record-badge').textContent = '0';
      syncGenerationStatusTimer();
      if (S.currentView === 'record') renderRecordView();
      if (S.currentView === 'dashboard') refreshDashboard();
      if (S.currentView === 'projects') loadProjects();
      showToast('稽核問題已產生完成', 'success');
      return;
    }

    try {
      S.questions = await api('GET', `/projects/${projectId}/questions`);
      if (S.projectId === projectId) {
        S.project = await api('GET', `/projects/${projectId}`);
        $('#project-name-display').textContent = S.project.name;
      }
    } catch (_) {}

    S.questionGeneration = {
      ...S.questionGeneration,
      jobId,
      projectId,
      status: 'error',
      message: job.message || '產生問題失敗',
      questionCount: S.questions.length || job.question_count || job.result_count || 0,
      targetCount: S.project?.question_count || 0,
      promise: null,
    };
    $('#nav-record-badge').textContent = '!';
    syncGenerationStatusTimer();
    if (S.currentView === 'record') renderRecordView();
    if (S.currentView === 'projects') loadProjects();
    showToast(S.questionGeneration.message);
  } catch (e) {
    S.questionGeneration = {
      ...S.questionGeneration,
      jobId,
      projectId,
      status: 'running',
      message: `暫時無法取得進度，稍後重試：${e.message}`,
    };
    if (S.currentView === 'record') renderRecordEmptyState();
  }
}

// ─── Record View ─────────────────────────────────────────
function renderRecordView() {
  syncGenerationStatusTimer();
  if (!S.questions.length) {
    $('#record-empty').classList.remove('hidden');
    $('#record-content').classList.add('hidden');
    renderRecordEmptyState();
    return;
  }
  $('#record-empty').classList.add('hidden');
  $('#record-content').classList.remove('hidden');
  renderQuestionGenerationWarning();
  updateProgress();
  renderQuestionPanels();
}

function syncGenerationStatusTimer() {
  const shouldRun = S.currentView === 'record' && S.questionGeneration.status === 'running';
  if (shouldRun && !S.generationStatusTimer) {
    S.generationStatusTimer = setInterval(() => {
      if (S.currentView === 'record' && S.questionGeneration.status === 'running') {
        renderRecordEmptyState();
      }
    }, 1000);
  }
  if (!shouldRun && S.generationStatusTimer) {
    clearInterval(S.generationStatusTimer);
    S.generationStatusTimer = null;
  }
}

function renderRecordEmptyState() {
  const el = $('#record-empty');
  const job = S.questionGeneration;
  const isCurrentJob = job.projectId && job.projectId === S.projectId;

  if (isCurrentJob && job.status === 'running') {
    const elapsed = job.startedAt ? Math.max(1, Math.round((Date.now() - job.startedAt) / 1000)) : 0;
    el.innerHTML = `
      <div class="spinner" style="margin:0 auto 16px"></div>
      <div class="empty-state-title">正在產生稽核問題</div>
      <div class="empty-state-desc">${esc(job.message)}<br>已執行約 ${elapsed} 秒</div>
      <button class="btn btn-ghost" onclick="navigate('projects')">先看其他專案</button>
    `;
    return;
  }

  if (isCurrentJob && job.status === 'error') {
    const target = Number(job.targetCount || S.project?.question_count || 0);
    const actual = Number(job.questionCount || S.questions.length || 0);
    const countLine = target ? `已產出 ${actual} / 目標 ${target} 題` : `已產出 ${actual} 題`;
    el.innerHTML = `
      <div class="empty-state-icon">!</div>
      <div class="empty-state-title">產生失敗</div>
      <div class="empty-state-desc">${esc(countLine)}<br>${esc(job.message)}</div>
      <div class="flex gap-8" style="justify-content:center">
        <button class="btn btn-primary" onclick="startQuestionGeneration('${S.projectId}')">重新產生</button>
        <button class="btn btn-ghost" onclick="addNewQuestion()">手動新增問題</button>
      </div>
    `;
    return;
  }

  el.innerHTML = `
    <div class="empty-state-icon">📝</div>
    <div class="empty-state-title">尚未產生稽核問題</div>
    <div class="empty-state-desc">請先完成專案設定</div>
    <button class="btn btn-primary" onclick="navigate('setup')">前往專案設定</button>
  `;
}

function renderQuestionGenerationWarning() {
  const el = $('#question-generation-warning');
  if (!el) return;
  const job = S.questionGeneration;
  const isCurrentJob = job.projectId && job.projectId === S.projectId;
  const target = Number(job.targetCount || S.project?.question_count || 0);
  const actual = Number(S.questions.length || job.questionCount || 0);

  if (!isCurrentJob || job.status !== 'error' || !target || actual >= target) {
    el.classList.add('hidden');
    el.innerHTML = '';
    return;
  }

  el.classList.remove('hidden');
  el.innerHTML = `
    <div>
      <div class="alert-title">稽核問題只產出 ${actual} / ${target} 題</div>
      <div class="alert-desc">${esc(job.message || 'LLM 回傳題數不足，系統已保留有效題目。')}</div>
    </div>
    <div class="flex gap-8 flex-wrap">
      <button class="btn btn-ghost btn-sm" onclick="startQuestionGeneration('${S.projectId}')">重新產生不足題數</button>
      <button class="btn btn-ghost btn-sm" onclick="addNewQuestion()">手動新增問題</button>
    </div>
  `;
}

function updateProgress() {
  const total = S.questions.length;
  const done = S.questions.filter(q => q.compliance_status).length;
  $('#record-progress').textContent = `進度：${done} / ${total}`;
  $('#progress-bar').style.width = total ? `${(done / total * 100).toFixed(0)}%` : '0%';
  $('#nav-record-badge').textContent = done;
}

function renderQuestionPanels() {
  const el = $('#question-panels');
  el.innerHTML = S.questions.map((q, i) => {
    const status = q.compliance_status || 'pending';
    const isActive = i === S.activeQuestionIndex;
    return `
    <div class="q-card ${isActive ? 'active' : ''} mb-12 fade-in" id="qcard-${i}">
      <div class="q-card-header" onclick="toggleQuestion(${i})">
        <span class="q-num">Q${i + 1}</span>
        <span class="q-title">${esc(q.text?.slice(0, 80) || '')}</span>
        <span class="q-status-dot ${status}"></span>
        <button class="btn-icon-sm" onclick="event.stopPropagation();deleteQuestion(${i})" title="刪除此題">✕</button>
      </div>
      ${isActive ? renderQuestionBody(q, i) : ''}
    </div>`;
  }).join('');
  loadQuickPhrases();
}

function renderQuestionBody(q, idx) {
  const status = q.compliance_status || '';
  const statuses = [
    { val: 'compliant', label: '✓ 符合' },
    { val: 'partial', label: '△ 部分符合' },
    { val: 'non_compliant', label: '✗ 不符合' },
    { val: 'not_applicable', label: '— 不適用' },
  ];
  return `
  <div class="q-card-body">
    <div class="q-text">${esc(q.text || '')}</div>
    <div class="flex gap-8 mb-8">
      <button class="btn btn-ghost btn-sm" onclick="editQuestionText(${idx})">✎ 編輯問題</button>
    </div>
    <div class="flex gap-8 mb-12">
      ${q.category ? `<span class="tag tag-category">${esc(q.category)}</span>` : ''}
      ${q.source_framework ? `<span class="tag tag-framework">${esc(q.source_framework)}</span>` : ''}
      ${q.reference ? `<span class="tag tag-reference">${esc(q.reference)}</span>` : ''}
    </div>
    <div class="form-group">
      <label class="form-label">合規狀態</label>
      <div class="status-bar">
        ${statuses.map(s => `<button class="status-btn ${status === s.val ? 'active' : ''}" data-status="${s.val}" onclick="setStatus(${idx},'${s.val}')">${s.label}</button>`).join('')}
      </div>
    </div>
    <div class="form-group">
      <label class="form-label">受稽回覆</label>
      <div id="phrases-${idx}" class="phrases-bar"></div>
      <textarea class="form-textarea" id="resp-${idx}" rows="4" placeholder="記錄受稽單位的回覆..." oninput="autoSaveQuestion(${idx})">${esc(q.response_text || '')}</textarea>
    </div>
    <div class="form-group">
      <label class="form-label">稽核員備註</label>
      <textarea class="form-textarea" id="notes-${idx}" rows="2" placeholder="稽核員觀察與備註..." oninput="autoSaveQuestion(${idx})">${esc(q.auditor_notes || '')}</textarea>
    </div>
  </div>`;
}

function toggleQuestion(idx) {
  S.activeQuestionIndex = S.activeQuestionIndex === idx ? -1 : idx;
  renderQuestionPanels();
}

function setStatus(idx, status) {
  const q = S.questions[idx];
  q.compliance_status = q.compliance_status === status ? null : status;
  updateProgress();
  renderQuestionPanels();
  saveQuestion(idx);
}

// ─── Question CRUD ───────────────────────────────────────
async function deleteQuestion(idx) {
  const q = S.questions[idx];
  if (!q) return;
  if (!confirm(`確定刪除 Q${idx + 1}？`)) return;
  try {
    await api('DELETE', `/questions/${q.id}`);
    S.questions.splice(idx, 1);
    if (S.activeQuestionIndex >= S.questions.length) S.activeQuestionIndex = Math.max(0, S.questions.length - 1);
    updateProgress();
    renderQuestionPanels();
    showToast('已刪除', 'success');
  } catch (e) { showToast('刪除失敗：' + e.message); }
}

async function addNewQuestion() {
  if (!S.projectId) return;
  const text = prompt('請輸入問題內容：');
  if (!text?.trim()) return;
  try {
    const q = await api('POST', `/projects/${S.projectId}/questions`, { text: text.trim() });
    S.questions.push(q);
    S.activeQuestionIndex = S.questions.length - 1;
    updateProgress();
    renderQuestionPanels();
    showToast('已新增問題', 'success');
  } catch (e) { showToast('新增失敗：' + e.message); }
}

async function editQuestionText(idx) {
  const q = S.questions[idx];
  if (!q) return;
  const newText = prompt('編輯問題內容：', q.text);
  if (newText === null || newText.trim() === q.text) return;
  try {
    await api('PATCH', `/questions/${q.id}`, { text: newText.trim() });
    q.text = newText.trim();
    renderQuestionPanels();
    showToast('已更新', 'success');
  } catch (e) { showToast('更新失敗：' + e.message); }
}

// ─── Quick Phrases ───────────────────────────────────────
async function loadQuickPhrases() {
  if (S.quickPhrases.length === 0) {
    try { S.quickPhrases = await api('GET', '/quick-phrases'); } catch (_) {}
  }
  S.questions.forEach((_, i) => {
    const el = document.getElementById(`phrases-${i}`);
    if (!el) return;
    el.innerHTML = S.quickPhrases.map(p =>
      `<button class="phrase-chip" onclick="insertPhrase(${i},'${esc(p.text)}')">${esc(p.text.slice(0, 15))}</button>`
    ).join('');
  });
}

function insertPhrase(idx, text) {
  const ta = document.getElementById(`resp-${idx}`);
  if (!ta) return;
  const start = ta.selectionStart;
  ta.value = ta.value.slice(0, start) + text + ta.value.slice(ta.selectionEnd);
  ta.focus();
  ta.selectionStart = ta.selectionEnd = start + text.length;
  autoSaveQuestion(idx);
}

// ─── Auto-save ───────────────────────────────────────────
function autoSaveQuestion(idx) {
  clearTimeout(S.autoSaveTimer);
  S.autoSaveTimer = setTimeout(() => saveQuestion(idx), 800);
}

async function saveQuestion(idx) {
  const q = S.questions[idx];
  const respEl = document.getElementById(`resp-${idx}`);
  const notesEl = document.getElementById(`notes-${idx}`);
  if (respEl) q.response_text = respEl.value;
  if (notesEl) q.auditor_notes = notesEl.value;

  $('#auto-save-status').textContent = '儲存中...';
  try {
    await api('PATCH', `/questions/${q.id}`, {
      compliance_status: q.compliance_status,
      response_text: q.response_text,
      auditor_notes: q.auditor_notes,
    });
    $('#auto-save-status').textContent = '✓ 已儲存';
    setTimeout(() => { $('#auto-save-status').textContent = ''; }, 2000);
  } catch (_) {
    $('#auto-save-status').textContent = '⚠ 儲存失敗';
  }
}

// ─── Report ──────────────────────────────────────────────
function onFormatChange(val) { S.reportFormat = val; }

async function loadReportList() {
  if (!S.projectId) return;
  try {
    S.reportList = await api('GET', `/projects/${S.projectId}/findings`);
  } catch (_) { S.reportList = []; }
  const sel = $('#report-history');
  if (!sel) return;
  if (!S.reportList.length) {
    sel.innerHTML = '<option value="">無歷史報告</option>';
    return;
  }
  sel.innerHTML = S.reportList.map((r, i) => {
    const date = r.created_at?.slice(0, 19).replace('T', ' ') || '';
    const fmt = r.report_format === 'gov' ? '政府' : 'IIA5C';
    const count = r.report_data?.findings?.length || 0;
    return `<option value="${esc(r.id)}" ${r.id === S.selectedFindingId ? 'selected' : ''}>${fmt} ${date} (${count}項)</option>`;
  }).join('');
}

async function loadReportById(findingId) {
  if (!findingId) return;
  try {
    const report = await api('GET', `/findings/${findingId}`);
    S.selectedFindingId = findingId;
    S.findings = report.report_data;
    S.findingsFormat = report.report_format;
    S.reportFormat = report.report_format;
    const fmtSel = $('#report-format');
    if (fmtSel) fmtSel.value = S.reportFormat;
    renderFindings();
  } catch (e) { showToast('載入報告失敗：' + e.message); }
}

async function deleteCurrentReport() {
  if (!S.selectedFindingId) { showToast('請先選擇報告'); return; }
  if (!confirm('確定刪除此份報告？')) return;
  try {
    await api('DELETE', `/findings/${S.selectedFindingId}`);
    S.findings = null;
    S.selectedFindingId = null;
    await loadReportList();
    if (S.reportList.length) {
      await loadReportById(S.reportList[0].id);
    } else {
      renderReportView();
    }
    showToast('報告已刪除', 'success');
  } catch (e) { showToast('刪除失敗：' + e.message); }
}

async function saveReportEdit() {
  if (!S.selectedFindingId || !S.findings) return;
  try {
    await api('PATCH', `/findings/${S.selectedFindingId}`, S.findings);
    showToast('報告已儲存', 'success');
  } catch (e) { showToast('儲存失敗：' + e.message); }
}

function editFindingSummary() {
  if (!S.findings) return;
  const newText = prompt('編輯摘要：', S.findings.executive_summary || '');
  if (newText === null) return;
  S.findings.executive_summary = newText;
  renderFindings();
  saveReportEdit();
}

function editFindingField(findingIdx, field) {
  if (!S.findings?.findings?.[findingIdx]) return;
  const fd = S.findings.findings[findingIdx];
  const newText = prompt(`編輯 ${field}：`, fd[field] || '');
  if (newText === null) return;
  fd[field] = newText;
  renderFindings();
  saveReportEdit();
}

function deleteFindingItem(findingIdx) {
  if (!S.findings?.findings) return;
  if (!confirm(`確定刪除第 ${findingIdx + 1} 項發現？`)) return;
  S.findings.findings.splice(findingIdx, 1);
  renderFindings();
  saveReportEdit();
}

function renderFindings() {
  const el = $('#report-content');
  if (!S.findings) { el.innerHTML = '<div class="empty-state"><div class="empty-state-icon">📊</div><div class="empty-state-title">尚未產生報告</div></div>'; return; }

  const f = S.findings;
  let html = '';
  if (f.executive_summary) {
    html += `<div class="card mb-16"><div class="card-header"><div class="card-title">摘要</div><button class="btn btn-ghost btn-sm" onclick="editFindingSummary()">✎ 編輯</button></div><p style="white-space:pre-wrap;font-size:0.9rem;line-height:1.7">${esc(f.executive_summary)}</p></div>`;
  }

  const findings = f.findings || [];
  if (S.reportFormat === 'gov') {
    html += findings.map((fd, i) => `
      <div class="finding-card mb-12 fade-in" data-risk="Medium">
        <div class="finding-header" onclick="this.nextElementSibling.classList.toggle('hidden')">
          <span style="font-weight:600;flex:1">${i + 1}. ${esc(fd.title || '')}</span>
          <span class="risk-badge Medium">${esc(fd.finding_type || '')}</span>
          <button class="btn-icon-sm" onclick="event.stopPropagation();deleteFindingItem(${i})" title="刪除此項">✕</button>
        </div>
        <div class="finding-body">
          <div class="flex gap-8 mb-8">
            <button class="btn btn-ghost btn-sm" onclick="editFindingField(${i},'title')">✎ 標題</button>
            <button class="btn btn-ghost btn-sm" onclick="editFindingField(${i},'finding_type')">✎ 類型</button>
            <button class="btn btn-ghost btn-sm" onclick="editFindingField(${i},'legal_basis')">✎ 法規</button>
            <button class="btn btn-ghost btn-sm" onclick="editFindingField(${i},'finding_description')">✎ 說明</button>
            <button class="btn btn-ghost btn-sm" onclick="editFindingField(${i},'recommendation')">✎ 建議</button>
          </div>
          ${fd.legal_basis ? `<div class="finding-section"><div class="finding-section-title">法規依據</div><div class="finding-legal"><p style="font-size:0.85rem">${esc(fd.legal_basis)}</p>${fd.legal_text ? `<p class="text-xs text-muted mt-8">${esc(fd.legal_text)}</p>` : ''}</div></div>` : ''}
          ${fd.finding_description ? `<div class="finding-section"><div class="finding-section-title">發現說明</div><p style="font-size:0.85rem;white-space:pre-wrap">${esc(fd.finding_description)}</p></div>` : ''}
          ${fd.recommendation ? `<div class="finding-section"><div class="finding-section-title">建議改善</div><div class="finding-recommendation"><p style="font-size:0.85rem">${esc(fd.recommendation)}</p></div></div>` : ''}
        </div>
      </div>`).join('');
  } else {
    html += findings.map((fd, i) => `
      <div class="finding-card mb-12 fade-in" data-risk="${esc(fd.risk_level || 'Medium')}">
        <div class="finding-header" onclick="this.nextElementSibling.classList.toggle('hidden')">
          <span style="font-weight:600;flex:1">${i + 1}. ${esc(fd.title || '')}</span>
          <span class="risk-badge ${esc(fd.risk_level || '')}">${esc(fd.risk_level || '')}</span>
          <button class="btn-icon-sm" onclick="event.stopPropagation();deleteFindingItem(${i})" title="刪除此項">✕</button>
        </div>
        <div class="finding-body">
          <div class="flex gap-8 mb-8">
            <button class="btn btn-ghost btn-sm" onclick="editFindingField(${i},'title')">✎ 標題</button>
            <button class="btn btn-ghost btn-sm" onclick="editFindingField(${i},'risk_level')">✎ 風險</button>
            <button class="btn btn-ghost btn-sm" onclick="editFindingField(${i},'condition')">✎ 現況</button>
            <button class="btn btn-ghost btn-sm" onclick="editFindingField(${i},'recommendation')">✎ 建議</button>
          </div>
          ${fd.criteria ? `<div class="finding-section"><div class="finding-section-title">Criteria 標準</div><p style="font-size:0.85rem">${esc(fd.criteria)}</p></div>` : ''}
          ${fd.condition ? `<div class="finding-section"><div class="finding-section-title">Condition 現況</div><p style="font-size:0.85rem">${esc(fd.condition)}</p></div>` : ''}
          ${fd.cause ? `<div class="finding-section"><div class="finding-section-title">Cause 原因</div><p style="font-size:0.85rem">${esc(fd.cause)}</p></div>` : ''}
          ${fd.effect ? `<div class="finding-section"><div class="finding-section-title">Consequence 影響</div><p style="font-size:0.85rem">${esc(fd.effect)}</p></div>` : ''}
          ${fd.recommendation ? `<div class="finding-section"><div class="finding-section-title">Corrective Action 建議</div><div class="finding-recommendation"><p style="font-size:0.85rem">${esc(fd.recommendation)}</p></div></div>` : ''}
          ${fd.regulatory_reference ? `<div class="finding-section"><div class="finding-section-title">法規依據</div><div class="finding-legal"><p style="font-size:0.85rem">${esc(fd.regulatory_reference)}</p></div></div>` : ''}
        </div>
      </div>`).join('');
  }
  el.innerHTML = html;
}

// ─── Utils ───────────────────────────────────────────────
async function renderReportView() {
  syncReportStatusTimer();
  if (S.findings) {
    renderFindings();
    return;
  }

  // Try loading the latest report from DB if we have a project
  if (S.projectId && S.reportGeneration.status !== 'running') {
    try {
      await loadReportList();
      if (S.reportList.length && !S.findings) {
        await loadReportById(S.reportList[0].id);
        if (S.findings) return;
      }
    } catch (_) {}
  }

  const el = $('#report-content');
  const job = S.reportGeneration;
  const isCurrentJob = job.projectId && job.projectId === S.projectId;

  if (isCurrentJob && job.status === 'running') {
    const elapsed = job.startedAt ? Math.max(1, Math.round((Date.now() - job.startedAt) / 1000)) : 0;
    el.innerHTML = `
      <div class="empty-state">
        <div class="spinner" style="margin:0 auto 16px"></div>
        <div class="empty-state-title">正在產生稽核報告</div>
        <div class="empty-state-desc">${esc(job.message)}<br>已執行約 ${elapsed} 秒</div>
        <button class="btn btn-ghost" onclick="navigate('projects')">先看其他專案</button>
      </div>
    `;
    return;
  }

  if (isCurrentJob && job.status === 'error') {
    el.innerHTML = `
      <div class="card" style="color:var(--danger)">
        ${esc(job.message)}
        <br>
        <button class="btn btn-primary btn-sm mt-12" onclick="generateReport()">重新產生</button>
      </div>
    `;
    return;
  }

  el.innerHTML = '<div class="empty-state"><div class="empty-state-icon">📊</div><div class="empty-state-title">尚未產生報告</div><div class="empty-state-desc">完成記錄後點擊「產生報告」</div></div>';
}

function syncReportStatusTimer() {
  const shouldRun = S.currentView === 'report' && S.reportGeneration.status === 'running';
  if (shouldRun && !S.reportStatusTimer) {
    S.reportStatusTimer = setInterval(() => {
      if (S.currentView === 'report' && S.reportGeneration.status === 'running') {
        renderReportView();
      }
    }, 1000);
  }
  if (!shouldRun && S.reportStatusTimer) {
    clearInterval(S.reportStatusTimer);
    S.reportStatusTimer = null;
  }
}

function generateReport() {
  if (!S.projectId || !S.questions.length) {
    showToast('請先完成稽核記錄');
    return;
  }
  if (S.reportGeneration.status === 'running' && S.reportGeneration.projectId === S.projectId) {
    showToast('稽核報告已在背景產生中，可先切到其他頁面', 'success');
    renderReportView();
    return;
  }

  clearReportPollTimer();
  const projectId = S.projectId;
  const format = S.reportFormat;
  S.findings = null;
  S.findingsFormat = null;
  S.reportGeneration = {
    projectId,
    jobId: null,
    status: 'running',
    format,
    message: 'AI 正在背景產生稽核報告，可先切到其他頁面',
    startedAt: Date.now(),
    promise: null,
  };

  renderReportView();
  showToast('已開始在背景產生稽核報告', 'success');

  const promise = api('POST', `/projects/${projectId}/findings/jobs?format=${encodeURIComponent(format)}`)
    .then((job) => {
      S.reportGeneration = {
        ...S.reportGeneration,
        jobId: job.job_id,
        message: job.message || S.reportGeneration.message,
      };
      pollReportGeneration(job.job_id, projectId, format);
      S.reportPollTimer = setInterval(() => pollReportGeneration(job.job_id, projectId, format), 2000);
    })
    .catch((e) => {
      S.reportGeneration = {
        ...S.reportGeneration,
        status: 'error',
        message: `啟動報告任務失敗：${e.message}`,
        promise: null,
      };
      syncReportStatusTimer();
      if (S.currentView === 'report') renderReportView();
      showToast(S.reportGeneration.message);
    });
  S.reportGeneration.promise = promise.catch(() => {});
}

function clearReportPollTimer() {
  if (S.reportPollTimer) {
    clearInterval(S.reportPollTimer);
    S.reportPollTimer = null;
  }
}

async function pollReportGeneration(jobId, projectId, format) {
  if (!jobId) return;
  try {
    const job = await api('GET', `/finding-jobs/${jobId}`);
    if (job.status === 'running') {
      S.reportGeneration = {
        ...S.reportGeneration,
        jobId,
        projectId,
        status: 'running',
        format,
        message: job.message || 'AI 正在背景產生稽核報告，可先切到其他頁面',
      };
      if (S.currentView === 'report') renderReportView();
      return;
    }

    clearReportPollTimer();
    if (job.status === 'done') {
      const reports = await api('GET', `/projects/${projectId}/findings`);
      const latest = reports.find(r => r.report_format === format) || reports[0];
      S.findings = latest?.report_data || null;
      S.findingsFormat = format;
      S.reportFormat = format;
      S.reportGeneration = {
        ...S.reportGeneration,
        jobId,
        status: 'done',
        message: '稽核報告已產生完成',
        promise: null,
      };
      syncReportStatusTimer();
      if (S.currentView === 'report') renderFindings();
      if (S.currentView === 'projects') loadProjects();
      showToast('稽核報告已產生完成', 'success');
      return;
    }

    S.reportGeneration = {
      ...S.reportGeneration,
      jobId,
      status: 'error',
      message: job.message || '報告產生失敗',
      promise: null,
    };
    syncReportStatusTimer();
    if (S.currentView === 'report') renderReportView();
    if (S.currentView === 'projects') loadProjects();
    showToast(S.reportGeneration.message);
  } catch (e) {
    S.reportGeneration = {
      ...S.reportGeneration,
      jobId,
      projectId,
      status: 'running',
      format,
      message: `暫時無法取得報告進度，稍後重試：${e.message}`,
    };
    if (S.currentView === 'report') renderReportView();
  }
}

// ─── Init ────────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', () => {
  getApiKey();
  const nameEl = $('#auditor-name');
  if (nameEl) {
    nameEl.value = getAuditorName();
    nameEl.addEventListener('change', () => setAuditorName(nameEl.value));
  }
  $('.sidebar-close-btn')?.addEventListener('click', closeSidebar);
  $('#sidebar-backdrop')?.addEventListener('click', closeSidebar);
  navigate('dashboard');
});

document.addEventListener('keydown', (event) => {
  if (event.key === 'Escape') closeSidebar();
});

// ─── Expose to HTML onclick ──────────────────────────────
window.navigate = navigate;
window.createNewProject = createNewProject;
window.openProject = openProject;
window.deleteProject = deleteProject;
window.toggleQuestion = toggleQuestion;
window.setStatus = setStatus;
window.insertPhrase = insertPhrase;
window.autoSaveQuestion = autoSaveQuestion;
window.startAudit = startAudit;
window.startQuestionGeneration = startQuestionGeneration;
window.applyTemplate = applyTemplate;
window.newFrameworkForm = newFrameworkForm;
window.selectFrameworkAdmin = selectFrameworkAdmin;
window.saveFramework = saveFramework;
window.deleteFrameworkAdmin = deleteFrameworkAdmin;
window.uploadFrameworkSource = uploadFrameworkSource;
window.saveControl = saveControl;
window.deleteControlAdmin = deleteControlAdmin;
window.deleteQuestion = deleteQuestion;
window.addNewQuestion = addNewQuestion;
window.editQuestionText = editQuestionText;
window.generateReport = generateReport;
window.onFormatChange = onFormatChange;
window.loadReportById = loadReportById;
window.deleteCurrentReport = deleteCurrentReport;
window.editFindingSummary = editFindingSummary;
window.editFindingField = editFindingField;
window.deleteFindingItem = deleteFindingItem;
window.toggleSidebar = toggleSidebar;
window.closeSidebar = closeSidebar;
