const state = {projects: [], documents: [], visible: [], project: '', current: '', projectEpoch: 0, readEpoch: 0, searchEpoch: 0};
const $ = selector => document.querySelector(selector);
const esc = value => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;', '<':'&lt;', '>':'&gt;', '"':'&quot;', "'":'&#39;'}[c]));
const storage = {
  get(key, fallback) { try { return JSON.parse(localStorage.getItem(key)) ?? fallback; } catch { return fallback; } },
  set(key, value) { try { localStorage.setItem(key, JSON.stringify(value)); } catch {} }
};
async function api(path, params = {}) {
  const response = await fetch(`${path}?${new URLSearchParams(params)}`);
  const data = await response.json();
  if (!response.ok) throw new Error(data.error || '读取失败，请刷新重试。');
  return data;
}
function toast(message) {
  $('#toast').textContent = message;
  $('#toast').classList.add('show');
  clearTimeout(toast.timer);
  toast.timer = setTimeout(() => $('#toast').classList.remove('show'), 3500);
}
function empty(title, message, error = false) {
  $('#content').innerHTML = `<div class="empty-state"><span class="empty-mark">V</span><h1>${esc(title)}</h1><p>${esc(message)}</p>${error ? '<p class="hint">可以在左侧重新选择项目或输入文件夹路径。</p>' : ''}</div>`;
}
function inline(text) {
  const pattern = /`([^`]+)`|\[([^\]]+)\]\(([^)]+)\)|\*\*([^*]+)\*\*/g;
  let html = '', end = 0;
  for (const match of text.matchAll(pattern)) {
    html += esc(text.slice(end, match.index));
    if (match[1] !== undefined) html += `<code>${esc(match[1])}</code>`;
    else if (match[4] !== undefined) html += `<strong>${esc(match[4])}</strong>`;
    else {
      const target = match[3].trim();
      if (/^https?:\/\//i.test(target)) html += `<a href="${esc(target)}" target="_blank" rel="noopener noreferrer">${esc(match[2])}</a>`;
      else if (!/^[a-z][a-z\d+.-]*:/i.test(target) && /\.md(?:#.*)?$/i.test(target)) html += `<a href="#" data-document-link="${esc(target.split('#')[0])}">${esc(match[2])}</a>`;
      else html += esc(match[2]);
    }
    end = match.index + match[0].length;
  }
  return html + esc(text.slice(end));
}
function markdown(raw) {
  const lines = String(raw || '').split(/\r?\n/);
  const html = [];
  let paragraph = [], list = [], listTag = 'ul';
  const flushParagraph = () => { if (paragraph.length) html.push(`<p>${paragraph.map(inline).join('<br>')}</p>`); paragraph = []; };
  const flushList = () => { if (list.length) html.push(`<${listTag}>${list.map(x => `<li>${inline(x)}</li>`).join('')}</${listTag}>`); list = []; };
  for (let i = 0; i < lines.length; i++) {
    const line = lines[i], fence = line.match(/^\s{0,3}(`{3,}|~{3,})/);
    if (fence) {
      flushParagraph(); flushList();
      const code = [], closing = new RegExp(`^ {0,3}${fence[1][0]}{${fence[1].length},}\\s*$`);
      while (++i < lines.length && !closing.test(lines[i])) code.push(lines[i]);
      html.push(`<pre><code>${esc(code.join('\n'))}</code></pre>`); continue;
    }
    const heading = line.match(/^(#{1,6})\s+(.+?)\s*#*\s*$/);
    if (heading) { flushParagraph(); flushList(); html.push(`<h${heading[1].length}>${inline(heading[2])}</h${heading[1].length}>`); continue; }
    if (line.includes('|') && i + 1 < lines.length && /^\s*\|?\s*:?-{3,}:?\s*\|/.test(lines[i + 1])) {
      flushParagraph(); flushList();
      const cells = row => row.trim().replace(/^\||\|$/g, '').split('|').map(x => x.trim());
      const head = cells(line), rows = [];
      i++;
      while (i + 1 < lines.length && lines[i + 1].includes('|') && lines[i + 1].trim()) rows.push(cells(lines[++i]));
      html.push(`<div class="table-wrap"><table><thead><tr>${head.map(x => `<th>${inline(x)}</th>`).join('')}</tr></thead><tbody>${rows.map(row => `<tr>${row.map(x => `<td>${inline(x)}</td>`).join('')}</tr>`).join('')}</tbody></table></div>`); continue;
    }
    const item = line.match(/^\s*(?:[-*+] |\d+\. )(.+)$/);
    if (item) { flushParagraph(); const tag = /^\s*\d/.test(line) ? 'ol' : 'ul'; if (tag !== listTag) flushList(); listTag = tag; list.push(item[1]); continue; }
    flushList();
    if (!line.trim()) { flushParagraph(); continue; }
    if (/^\s*([-*_])(?:\s*\1){2,}\s*$/.test(line)) { flushParagraph(); html.push('<hr>'); continue; }
    if (line.startsWith('> ')) { flushParagraph(); html.push(`<blockquote>${inline(line.slice(2))}</blockquote>`); continue; }
    paragraph.push(line);
  }
  flushParagraph(); flushList();
  return html.join('');
}
function projectPicker() {
  $('#projectSelect').innerHTML = '<option value="">选择已有项目</option>' + state.projects.map(p => `<option value="${esc(p.path)}">${esc(p.title || p.id || p.path)}</option>`).join('');
  $('#projectSelect').value = state.project;
}
function group(doc) {
  if (doc.archived || doc.status === 'done') return '历史记录';
  return {overview:'项目概览', module:'模块知识', continuation:'进行中的任务'}[doc.type] || '其他文档';
}
function renderList(documents = state.visible) {
  state.visible = documents;
  $('#documentList').innerHTML = ['项目概览', '模块知识', '进行中的任务', '历史记录', '其他文档'].map(name => {
    const rows = documents.filter(doc => group(doc) === name);
    return rows.length ? `<div class="group-title"><span>${name}</span><span>${rows.length}</span></div>${rows.map(doc => `<button class="document-item ${state.current === doc.path ? 'active' : ''}" data-path="${esc(doc.path)}" ${state.current === doc.path ? 'aria-current="page"' : ''}><strong>${esc(doc.title || doc.id || doc.path)}</strong><small>${esc(doc.path.replace(/^\.handoff\//, ''))}</small></button>`).join('')}` : '';
  }).join('') || '<p class="hint">没有匹配的交接文件。</p>';
}
async function openProject(rawPath, keep = '') {
  const requested = rawPath.trim().replace(/^['"]|['"]$/g, '');
  if (!requested) return;
  const epoch = ++state.projectEpoch;
  state.readEpoch++; state.searchEpoch++;
  state.project = requested; state.current = ''; state.documents = []; state.visible = [];
  $('#searchInput').value = ''; $('#searchInput').disabled = true;
  $('#documentList').innerHTML = '<p class="hint">正在读取交接目录…</p>';
  $('#documentCount').textContent = '正在读取…';
  $('#projectPath').textContent = requested;
  empty('正在打开项目', '读取本地交接文件。');
  try {
    const data = await api('/api/documents', {project: requested});
    if (epoch !== state.projectEpoch) return;
    state.project = data.project; state.documents = data.documents;
    state.projects = [{path: data.project, title: data.title}, ...state.projects.filter(p => p.path !== data.project)];
    const previous = storage.get('vervision-recent-projects', []);
    storage.set('vervision-recent-projects', [{path: data.project, title: data.title}, ...(Array.isArray(previous) ? previous : []).filter(p => p.path !== data.project)].slice(0, 8));
    storage.set('vervision-last-project', data.project);
    projectPicker(); $('#pathInput').value = '';
    $('#projectPath').textContent = data.project;
    $('#documentCount').textContent = `${data.documents.length} 份交接文件 · 只读`;
    $('#searchInput').disabled = false;
    renderList(data.documents);
    if (data.warnings.length) toast(`${data.warnings.length} 份文件无法读取：${data.warnings[0]}`);
    const selected = data.documents.find(d => d.path === keep) || data.documents.find(d => d.type === 'overview') || data.documents[0];
    if (selected) await showDocument(selected.path);
    else empty('这里还没有交接文档', '.handoff 文件夹中没有 Markdown 文件。你可以打开另一个已有交接的项目。');
  } catch (error) {
    if (epoch !== state.projectEpoch) return;
    $('#documentList').innerHTML = ''; $('#documentCount').textContent = '项目未打开';
    empty('未能打开这个项目', error.message, true);
  }
}
const sourceLabels = {FRESH:['来源未变化','solved'], STALE:['来源已变化','pending'], UNVERIFIED:['尚未核验','review']};
const statusLabels = {done:'已完成 · 历史记录', open:'进行中', blocked:'受阻'};
function sourceDetails(doc) {
  const freshness = doc.freshness;
  const sources = Array.isArray(doc.sources) ? doc.sources : [];
  const rules = [['业务约定', doc.business_rules], ['固定约束', doc.invariants], ['相关模块', doc.related_modules]];
  if (!freshness && !sources.length && !rules.some(([,items]) => items?.length)) return '';
  let changes = '';
  if (freshness) changes = freshness.changed_sources == null ? '尚无逐文件核验基线。' : freshness.changed_sources.length ? `<ul>${freshness.changed_sources.map(x => `<li>${esc({added:'新增', modified:'修改', removed:'移除'}[x.change] || x.change)} · ${esc(x.path)}</li>`).join('')}</ul>` : '登记来源自核验以来未变化。';
  return `<details class="metadata"><summary>来源与核验详情${sources.length ? ` · ${sources.length} 项来源` : ''}</summary><p>来源状态只说明文件变化，不证明内容正确或外部服务可用。</p>${freshness ? `<p>文档核验：${esc(freshness.document_verification.state)}<br>最近核验：${esc(freshness.verified_at || '尚无记录')}</p><h3>文件变化</h3><div>${changes}</div>` : ''}<h3>来源路径</h3><ul>${sources.map(path => `<li>${/\.md$/i.test(path) && !/[*?\[]/.test(path) ? `<button data-source-path="${esc(path)}">${esc(path)}</button>` : esc(path)}</li>`).join('')}</ul>${rules.filter(([,items]) => Array.isArray(items) && items.length).map(([title,items]) => `<h3>${title}</h3><ul>${items.map(x => `<li>${esc(x)}</li>`).join('')}</ul>`).join('')}</details>`;
}
async function showDocument(path) {
  const epoch = ++state.readEpoch, project = state.project;
  state.current = path;
  renderList();
  $('#content').innerHTML = '<p class="hint">正在读取文档…</p>';
  try {
    const doc = await api('/api/document', {project, path});
    if (epoch !== state.readEpoch || project !== state.project) return;
    state.current = doc.path;
    renderList();
    const source = doc.freshness ? sourceLabels[doc.freshness.state] || [doc.freshness.state, 'review'] : null;
    const history = doc.archived || doc.status === 'done';
    $('#content').innerHTML = `<article><header class="detail-head"><span class="eyebrow">${esc(group(doc))}</span><h1>${esc(doc.title || doc.path)}</h1>${doc.summary ? `<p class="summary">${esc(doc.summary)}</p>` : ''}<div class="badges">${source ? `<span class="badge ${source[1]}">${esc(source[0])}</span>` : ''}${doc.status ? `<span class="badge">${esc(statusLabels[doc.status] || doc.status)}</span>` : ''}${(Array.isArray(doc.tags) ? doc.tags : []).map(tag => `<span class="badge">${esc(tag)}</span>`).join('')}</div><div class="file-path">${esc(doc.path)}</div></header>${doc.notice ? `<p class="notice">${esc(doc.notice)}</p>` : ''}${history ? '<p class="notice">这是一份历史记录，其中的计划与约束仅代表当时的上下文。</p>' : ''}${doc.next_step && !history ? `<p class="notice">下一步 · ${esc(doc.next_step)}</p>` : ''}<section class="reader"><div class="markdown">${markdown(doc.body) || '<p class="hint">这份文档还没有正文。</p>'}</div></section>${sourceDetails(doc)}${Array.isArray(doc.external_checks) && doc.external_checks.length ? `<details class="metadata"><summary>记录中的外部检查</summary><ul>${doc.external_checks.map(check => `<li>${esc(check.service)} · ${esc(check.status)} · ${esc(check.checked_at)}<br>${esc(check.evidence)}</li>`).join('')}</ul></details>` : ''}</article>`;
  } catch (error) {
    if (epoch === state.readEpoch && project === state.project) empty('无法读取这份文档', error.message, true);
  }
}
$('#openForm').addEventListener('submit', event => { event.preventDefault(); openProject($('#pathInput').value); });
$('#projectSelect').addEventListener('change', event => openProject(event.target.value));
$('#documentList').addEventListener('click', event => { const button = event.target.closest('[data-path]'); if (button) showDocument(button.dataset.path); });
$('#content').addEventListener('click', event => {
  const source = event.target.closest('[data-source-path]');
  if (source) return showDocument(source.dataset.sourcePath);
  const link = event.target.closest('[data-document-link]');
  if (link) {
    event.preventDefault();
    const directory = state.current.slice(0, state.current.lastIndexOf('/') + 1);
    showDocument(directory + link.dataset.documentLink);
  }
});
let searchTimer;
$('#searchInput').addEventListener('input', () => {
  clearTimeout(searchTimer);
  const epoch = ++state.searchEpoch, project = state.project, query = $('#searchInput').value.trim();
  if (!query) return renderList(state.documents);
  searchTimer = setTimeout(async () => {
    try {
      const data = await api('/api/documents', {project, q:query});
      if (epoch === state.searchEpoch && project === state.project) renderList(data.documents);
    } catch (error) { if (epoch === state.searchEpoch) toast(error.message); }
  }, 180);
});
$('#refreshBtn').onclick = () => state.project ? openProject(state.project, state.current) : initialize();
$('#themeBtn').onclick = () => {
  const theme = document.documentElement.dataset.theme === 'dark' ? 'light' : 'dark';
  document.documentElement.dataset.theme = theme;
  try { localStorage.setItem('vervision-theme', theme); } catch {}
};
async function initialize() {
  try {
    const [health, projects] = await Promise.all([api('/api/health'), api('/api/projects')]);
    $('#version').textContent = `v${health.version}`;
    const recent = storage.get('vervision-recent-projects', []);
    state.projects = [...projects];
    for (const project of Array.isArray(recent) ? recent : []) if (!state.projects.some(p => p.path === project.path)) state.projects.push(project);
    projectPicker();
    const initial = storage.get('vervision-last-project', '') || projects.find(p => p.reasons?.includes('workspace'))?.path || state.projects[0]?.path;
    if (initial) await openProject(initial);
  } catch (error) { empty('本地服务暂时无法连接', `${error.message} 请重新运行启动脚本。`, true); }
}
initialize();
