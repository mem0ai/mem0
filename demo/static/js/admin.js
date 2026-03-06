/* ═══════════════════════════════════════════════════════════════════════
   Mem0 Admin Panel – Frontend Logic
   ═══════════════════════════════════════════════════════════════════════ */

const $ = id => document.getElementById(id);

let allMemories = [];
let filteredMemories = [];
let isSearchMode = false;

// ─── Init ─────────────────────────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', () => {
  loadUsers();
  loadMemories();
  bindEvents();
});

function bindEvents() {
  $('refreshBtn').addEventListener('click', () => {
    isSearchMode = false;
    $('searchQuery').value = '';
    loadUsers();
    loadMemories();
  });

  $('userFilter').addEventListener('change', applyFilters);

  $('searchBtn').addEventListener('click', doSearch);
  $('searchQuery').addEventListener('keydown', e => {
    if (e.key === 'Enter') doSearch();
  });

  $('clearSearchBtn').addEventListener('click', () => {
    $('searchQuery').value = '';
    isSearchMode = false;
    applyFilters();
  });

  $('deleteAllBtn').addEventListener('click', deleteAll);
}

// ─── Data Loading ──────────────────────────────────────────────────────────
async function loadUsers() {
  try {
    const res = await fetch('/api/admin/users');
    const data = await res.json();
    const sel = $('userFilter');
    const current = sel.value;
    sel.innerHTML = '<option value="">全部用户</option>';
    (data.users || []).forEach(u => {
      const opt = document.createElement('option');
      opt.value = u;
      opt.textContent = u;
      if (u === current) opt.selected = true;
      sel.appendChild(opt);
    });
    $('statUsers').textContent = (data.users || []).length;
  } catch (e) {
    console.error('Load users failed', e);
  }
}

async function loadMemories() {
  setTableLoading(true);
  try {
    const userId = $('userFilter').value;
    let url = '/api/admin/memories?limit=500';
    if (userId) url += `&user_id=${encodeURIComponent(userId)}`;

    const res = await fetch(url);
    const data = await res.json();
    allMemories = data.results || [];
    isSearchMode = false;
    applyFilters();
    $('statTotal').textContent = allMemories.length;
  } catch (e) {
    console.error('Load memories failed', e);
    showTableError('加载失败: ' + e.message);
  } finally {
    setTableLoading(false);
  }
}

async function doSearch() {
  const query = $('searchQuery').value.trim();
  if (!query) { isSearchMode = false; applyFilters(); return; }

  setTableLoading(true);
  try {
    const userId = $('userFilter').value;
    let url = `/api/admin/search?query=${encodeURIComponent(query)}&limit=50`;
    if (userId) url += `&user_id=${encodeURIComponent(userId)}`;

    const res = await fetch(url);
    const data = await res.json();
    isSearchMode = true;
    filteredMemories = data.results || [];
    renderTable(filteredMemories, query);
    $('statFiltered').textContent = filteredMemories.length;
  } catch (e) {
    showTableError('搜索失败: ' + e.message);
  } finally {
    setTableLoading(false);
  }
}

function applyFilters() {
  if (isSearchMode) return;
  const userId = $('userFilter').value;
  filteredMemories = userId
    ? allMemories.filter(m => m.user_id === userId)
    : [...allMemories];
  $('statFiltered').textContent = filteredMemories.length;
  renderTable(filteredMemories);
}

// ─── Table Rendering ───────────────────────────────────────────────────────
function renderTable(memories, searchQuery = '') {
  const tbody = $('memoryTableBody');

  if (!memories.length) {
    tbody.innerHTML = `<tr><td colspan="5">
      <div class="empty-state">
        <h3>🔍 暂无记忆数据</h3>
        <p>${searchQuery ? '没有找到匹配的记忆' : '还没有任何记忆，去对话页聊几句吧'}</p>
      </div>
    </td></tr>`;
    return;
  }

  tbody.innerHTML = memories.map(m => {
    const content = highlightText(escHtml(m.memory || ''), searchQuery);
    const userId = m.user_id || '—';
    const createdAt = formatTime(m.created_at);
    const updatedAt = formatTime(m.updated_at);
    const scoreTag = m.score != null
      ? `<span class="mem-score">相关度 ${m.score.toFixed(3)}</span>`
      : '';

    return `<tr>
      <td><span class="user-tag">${escHtml(userId)}</span></td>
      <td>
        <div class="mem-content">${content}${scoreTag}</div>
        <div class="mem-id">ID: ${m.id}</div>
      </td>
      <td class="time-cell">${createdAt}</td>
      <td class="time-cell">${updatedAt}</td>
      <td class="action-cell">
        <button class="btn btn-xs btn-outline" onclick="showDetail('${m.id}')">详情</button>
        <button class="btn btn-xs btn-danger" onclick="deleteMemory('${m.id}')">删除</button>
      </td>
    </tr>`;
  }).join('');
}

// ─── Memory Detail ─────────────────────────────────────────────────────────
async function showDetail(memId) {
  $('detailContent').textContent = '加载中…';
  $('detailMeta').textContent = '';
  $('detailHistory').innerHTML = '';
  $('detailModal').style.display = 'flex';

  const mem = allMemories.find(m => m.id === memId)
    || filteredMemories.find(m => m.id === memId);

  if (mem) {
    $('detailContent').textContent = mem.memory;
    const meta = { ...mem };
    delete meta.memory;
    $('detailMeta').textContent = JSON.stringify(meta, null, 2);
  }

  // Load history
  try {
    const res = await fetch(`/api/admin/memories/${memId}/history`);
    const data = await res.json();
    const history = data.history || [];

    if (!history.length) {
      $('detailHistory').innerHTML = '<p class="hint" style="padding:8px">暂无历史记录</p>';
      return;
    }

    $('detailHistory').innerHTML = history.map(h => `
      <div class="history-item ${h.event || ''}">
        <span class="history-event event-${h.event || 'NONE'}">${h.event || 'UNKNOWN'}</span>
        ${h.old_memory ? `<div class="history-old">旧: ${escHtml(h.old_memory)}</div>` : ''}
        ${h.new_memory ? `<div class="history-text">新: ${escHtml(h.new_memory)}</div>` : ''}
        <div class="history-time">${formatTime(h.updated_at || h.created_at)}</div>
      </div>`).join('');
  } catch (e) {
    $('detailHistory').innerHTML = `<p class="hint" style="color:var(--danger)">历史加载失败: ${e.message}</p>`;
  }
}

// ─── Delete Actions ────────────────────────────────────────────────────────
async function deleteMemory(memId) {
  if (!confirm('确定删除这条记忆？')) return;
  try {
    const res = await fetch(`/api/admin/memories/${memId}`, { method: 'DELETE' });
    if (!res.ok) throw new Error('Delete failed');
    await loadMemories();
    await loadUsers();
  } catch (e) {
    alert('删除失败: ' + e.message);
  }
}

async function deleteAll() {
  const userId = $('userFilter').value;
  const target = userId ? `用户「${userId}」的所有记忆` : '所有用户的全部记忆';
  if (!confirm(`⚠️ 确定删除${target}？此操作不可恢复！`)) return;

  try {
    let url = '/api/admin/memories';
    if (userId) url += `?user_id=${encodeURIComponent(userId)}`;
    const res = await fetch(url, { method: 'DELETE' });
    if (!res.ok) throw new Error('Delete all failed');
    await loadMemories();
    await loadUsers();
  } catch (e) {
    alert('清空失败: ' + e.message);
  }
}

// ─── Helpers ───────────────────────────────────────────────────────────────
function escHtml(t) {
  return String(t)
    .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
}

function highlightText(text, query) {
  if (!query) return text;
  const words = query.split(/\s+/).filter(Boolean);
  let result = text;
  words.forEach(word => {
    const escaped = word.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
    result = result.replace(
      new RegExp(`(${escaped})`, 'gi'),
      '<span class="highlight">$1</span>'
    );
  });
  return result;
}

function formatTime(ts) {
  if (!ts) return '—';
  try {
    const d = new Date(ts);
    return d.toLocaleString('zh-CN', {
      month: '2-digit', day: '2-digit',
      hour: '2-digit', minute: '2-digit',
    }).replace(/\//g, '-');
  } catch { return ts; }
}

function setTableLoading(loading) {
  const tbody = $('memoryTableBody');
  if (loading) {
    tbody.innerHTML = `<tr><td colspan="5" class="table-empty">
      <span class="spinner"></span>加载中…
    </td></tr>`;
  }
}

function showTableError(msg) {
  $('memoryTableBody').innerHTML = `<tr><td colspan="5" class="table-empty" style="color:var(--danger)">${escHtml(msg)}</td></tr>`;
}

// Expose for inline handlers
window.showDetail = showDetail;
window.deleteMemory = deleteMemory;
window.$ = $;
