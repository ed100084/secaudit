export function createProjectsModule(deps) {
  const {
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
  } = deps;

  async function loadProjects() {
    try {
      const list = await api('GET', '/projects');
      const el = $('#projects-list');
      if (!list.length) {
        el.innerHTML = '<div class="empty-state"><div class="empty-state-icon">📂</div><div class="empty-state-title">尚無專案</div></div>';
        return;
      }
      el.innerHTML = list.map(p => `
        <div class="card mb-12 fade-in" style="cursor:pointer" onclick="openProject('${p.id}')">
          <div class="flex items-center justify-between">
            <div>
              <div class="flex items-center gap-8" style="flex-wrap:wrap">
                <span style="font-weight:600">${esc(p.name)}</span>
                ${renderProjectJobBadges(p)}
              </div>
              <div class="text-xs text-muted mt-8">${esc(p.organization || '')} · ${p.status} · ${p.created_at?.slice(0,10) || ''}</div>
            </div>
            <button class="btn btn-ghost btn-sm" onclick="event.stopPropagation();deleteProject('${p.id}')">刪除</button>
          </div>
        </div>`).join('');
    } catch (e) { showToast('載入專案失敗：' + e.message); }
  }

  function renderProjectJobBadges(project) {
    const jobs = project.jobs || {};
    return [
      renderProjectJobBadge('問題', jobs.questions),
      renderProjectJobBadge('報告', jobs.report),
    ].filter(Boolean).join('');
  }

  function renderProjectJobBadge(label, job) {
    if (!job) return '';
    const statusMap = {
      running: '產生中',
      done: '已完成',
      error: '失敗',
    };
    const text = statusMap[job.status];
    if (!text) return '';
    const elapsed = formatJobElapsed(job);
    const details = [
      `${label}${text}`,
      job.created_at ? `開始：${formatJobTime(job.created_at)}` : '',
      job.updated_at ? `更新：${formatJobTime(job.updated_at)}` : '',
      job.finished_at ? `完成：${formatJobTime(job.finished_at)}` : '',
      elapsed ? `耗時：${elapsed}` : '',
      job.message || '',
    ].filter(Boolean).join('\n');
    return `<span class="job-badge job-${esc(job.status)}" title="${esc(details)}">${label}${text}${elapsed ? ` ${esc(elapsed)}` : ''}</span>`;
  }

  function formatJobTime(value) {
    const time = Date.parse(value || '');
    if (!Number.isFinite(time)) return '';
    return new Date(time).toLocaleString('zh-TW', {
      month: '2-digit',
      day: '2-digit',
      hour: '2-digit',
      minute: '2-digit',
    });
  }

  function formatJobElapsed(job) {
    const start = Date.parse(job.created_at || job.updated_at || '');
    const end = job.status === 'running'
      ? Date.now()
      : Date.parse(job.finished_at || job.updated_at || '');
    if (!Number.isFinite(start) || !Number.isFinite(end) || end < start) return '';
    const seconds = Math.max(1, Math.round((end - start) / 1000));
    if (seconds < 60) return `${seconds}秒`;
    const minutes = Math.floor(seconds / 60);
    if (minutes < 60) return `${minutes}分`;
    const hours = Math.floor(minutes / 60);
    const rest = minutes % 60;
    return rest ? `${hours}時${rest}分` : `${hours}時`;
  }

  async function createNewProject() {
    showLoading('建立專案...');
    try {
      const p = await api('POST', '/projects', {
        name: '',
        auditor_name: getAuditorName(),
        organization: '',
      });
      S.projectId = p.id;
      S.project = p;
      S.frameworks = [];
      S.questions = [];
      S.findings = null;
      S.findingsFormat = null;
      S.selectedFindingId = null;
      S.reportList = [];
      $('#project-name-display').textContent = p.name;
      navigate('setup');
      await Promise.all([loadFrameworks(), loadTemplates()]);
    } catch (e) { showToast('建立失敗：' + e.message); }
    finally { hideLoading(); }
  }

  async function openProject(id) {
    showLoading('載入專案...');
    try {
      S.projectId = id;
      S.project = await api('GET', `/projects/${id}`);
      S.questions = await api('GET', `/projects/${id}/questions`);
      $('#project-name-display').textContent = S.project.name;
      if (S.project.frameworks) S.frameworks = [...S.project.frameworks];
      fillSetupForm();
      restoreProjectJobs(S.project.jobs || {});
      if (S.questionGeneration.status === 'running' && S.questionGeneration.projectId === id) navigate('record');
      else if (S.questions.length > 0) navigate('record');
      else navigate('setup');
    } catch (e) { showToast('載入失敗：' + e.message); }
    finally { hideLoading(); }
  }

  async function deleteProject(id) {
    if (!confirm('確定要刪除此專案？')) return;
    try {
      await api('DELETE', `/projects/${id}`);
      if (S.projectId === id) { S.projectId = null; S.project = null; S.questions = []; }
      loadProjects();
    } catch (e) { showToast('刪除失敗：' + e.message); }
  }

  return {
    loadProjects,
    createNewProject,
    openProject,
    deleteProject,
  };
}
