/* ═══════════════════════════════════════════════════════════════════════
   Mem0 Demo – Main Frontend Logic
   ═══════════════════════════════════════════════════════════════════════ */

// ─── State ────────────────────────────────────────────────────────────────
const state = {
  sessionId: null,
  activeSkillId: null,
  skills: {},
  editingSkillId: null,
  lastMemories: [],
};

// ─── DOM Refs ─────────────────────────────────────────────────────────────
const $ = id => document.getElementById(id);
const messagesEl = $('messages');
const userInputEl = $('userInput');
const sendBtn = $('sendBtn');
const sessionBadgeEl = $('sessionBadge');
const sessionInfoEl = $('sessionInfo');
const memStatusEl = $('memStatus');
const activeSkillBar = $('activeSkillBar');
const activeSkillName = $('activeSkillName');
const promptHintEl = $('promptHint');

// ─── Init ─────────────────────────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', () => {
  initSession();
  loadSkills();
  bindEvents();
  showWelcome();
  updateMemStatus();
});

function initSession() {
  state.sessionId = crypto.randomUUID().slice(0, 8);
  sessionBadgeEl.textContent = `session: ${state.sessionId}`;
  sessionInfoEl.textContent = `会话 ID: ${state.sessionId}`;
}

function updateMemStatus() {
  const on = $('useMemory').checked;
  memStatusEl.textContent = on ? '🧠 记忆已启用' : '⚪ 记忆已关闭';
  memStatusEl.style.color = on ? 'var(--success)' : 'var(--text-dim)';
}

// ─── Welcome Screen ────────────────────────────────────────────────────────
function showWelcome() {
  messagesEl.innerHTML = `
    <div class="welcome-msg">
      <h2>🧠 Mem0 记忆对话 Demo</h2>
      <p>这个 Demo 展示 Mem0 如何为 AI 提供跨会话长期记忆。</p>
      <ul>
        <li>在左侧设置 <strong>User ID</strong>，记忆按用户隔离</li>
        <li>选择 <strong>Skill</strong> 可切换 AI 的能力模式</li>
        <li>编辑 <strong>System Prompt</strong> 自定义 AI 行为</li>
        <li>关闭「记忆增强」对比有无记忆的差异</li>
        <li>点击「查看记忆」查看本次检索到的记忆条目</li>
        <li>访问 <a href="/admin" target="_blank" style="color:var(--accent)">管理后台</a> 查看完整记忆库</li>
      </ul>
    </div>`;
}

// ─── Events ────────────────────────────────────────────────────────────────
function bindEvents() {
  sendBtn.addEventListener('click', sendMessage);
  userInputEl.addEventListener('keydown', e => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      sendMessage();
    }
  });
  // Auto-grow textarea
  userInputEl.addEventListener('input', () => {
    userInputEl.style.height = 'auto';
    userInputEl.style.height = Math.min(userInputEl.scrollHeight, 160) + 'px';
  });

  $('newSessionBtn').addEventListener('click', () => {
    if (messagesEl.querySelector('.msg') && !confirm('新建会话将清除当前聊天记录（记忆库不受影响），继续？')) return;
    initSession();
    showWelcome();
    state.lastMemories = [];
    $('showMemBtn').style.display = 'none';
    $('memoryPeek').style.display = 'none';
  });

  $('useMemory').addEventListener('change', updateMemStatus);
  $('addSkillBtn').addEventListener('click', () => openSkillModal(null));
  $('clearSkillBtn').addEventListener('click', clearActiveSkill);
  $('showMemBtn').addEventListener('click', showMemoryPeek);
}

// ─── Send Message ──────────────────────────────────────────────────────────
async function sendMessage() {
  const text = userInputEl.value.trim();
  if (!text) return;

  appendMessage('user', text);
  userInputEl.value = '';
  userInputEl.style.height = 'auto';

  const typingEl = appendTyping();
  sendBtn.disabled = true;

  try {
    const body = {
      message: text,
      user_id: $('userId').value.trim() || 'default_user',
      session_id: state.sessionId,
      system_prompt: $('systemPrompt').value.trim() || null,
      skill_id: state.activeSkillId || null,
      use_memory: $('useMemory').checked,
    };

    const res = await fetch('/api/chat', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    });

    if (!res.ok) {
      const err = await res.json();
      throw new Error(err.detail || 'API Error');
    }

    const data = await res.json();

    typingEl.remove();
    appendMessage('assistant', data.reply, data.memories_used);

    // Store last memories for peek panel
    state.lastMemories = data.memories_used || [];
    if (state.lastMemories.length > 0) {
      $('showMemBtn').style.display = 'inline-block';
    }

    // Update memory add result hint
    if (data.memory_add_result) {
      const added = (data.memory_add_result.results || []).filter(r => r.event !== 'NONE');
      if (added.length > 0) {
        appendSystemMsg(`✅ Mem0 已处理 ${added.length} 条记忆更新`);
      }
    }
  } catch (err) {
    typingEl.remove();
    appendMessage('assistant', `❌ 请求失败：${err.message}`);
  } finally {
    sendBtn.disabled = false;
    userInputEl.focus();
  }
}

// ─── Message Rendering ─────────────────────────────────────────────────────
function appendMessage(role, content, memories = []) {
  // Remove welcome if present
  const welcome = messagesEl.querySelector('.welcome-msg');
  if (welcome) welcome.remove();

  const div = document.createElement('div');
  div.className = `msg ${role}`;

  const avatar = role === 'user' ? '👤' : '🤖';
  const time = new Date().toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' });

  const memTag = (role === 'assistant' && memories.length > 0)
    ? `<span style="color:var(--accent);font-size:0.65rem">🧠 引用了 ${memories.length} 条记忆</span>`
    : '';

  div.innerHTML = `
    <div class="msg-avatar">${avatar}</div>
    <div>
      <div class="msg-bubble">${renderContent(content)}</div>
      <div class="msg-meta">${time} ${memTag}</div>
    </div>`;

  messagesEl.appendChild(div);
  messagesEl.scrollTop = messagesEl.scrollHeight;
  return div;
}

function appendTyping() {
  const div = document.createElement('div');
  div.className = 'msg assistant';
  div.innerHTML = `
    <div class="msg-avatar">🤖</div>
    <div><div class="msg-bubble"><div class="typing-dots"><span></span><span></span><span></span></div></div></div>`;
  messagesEl.appendChild(div);
  messagesEl.scrollTop = messagesEl.scrollHeight;
  return div;
}

function appendSystemMsg(text) {
  const div = document.createElement('div');
  div.className = 'system-msg';
  div.textContent = text;
  messagesEl.appendChild(div);
  messagesEl.scrollTop = messagesEl.scrollHeight;
}

function renderContent(text) {
  // Simple markdown: code blocks, inline code, bold, newlines
  return text
    .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
    .replace(/```(\w*)\n?([\s\S]*?)```/g, (_, lang, code) =>
      `<pre><code>${code.trim()}</code></pre>`)
    .replace(/`([^`]+)`/g, '<code>$1</code>')
    .replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>')
    .replace(/\n/g, '<br>');
}

// ─── Memory Peek ───────────────────────────────────────────────────────────
function showMemoryPeek() {
  const peek = $('memoryPeek');
  const list = $('memoryList');
  $('memCount').textContent = state.lastMemories.length;
  list.innerHTML = state.lastMemories.map(m => `
    <div class="memory-item">
      ${escHtml(m.memory)}
      <div class="memory-score">相关度: ${m.score ? m.score.toFixed(3) : 'N/A'} · ID: ${m.id?.slice(0,8)}…</div>
    </div>`).join('');
  peek.style.display = peek.style.display === 'none' ? 'flex' : 'none';
  peek.style.flexDirection = 'column';
}

function escHtml(t) {
  return String(t).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');
}

// ─── Skills ────────────────────────────────────────────────────────────────
async function loadSkills() {
  try {
    const res = await fetch('/api/skills');
    state.skills = await res.json();
    renderSkills();
  } catch (e) {
    console.error('Failed to load skills', e);
  }
}

function renderSkills() {
  const list = $('skillsList');
  const entries = Object.values(state.skills);
  if (!entries.length) {
    list.innerHTML = '<p class="hint" style="text-align:center;padding:8px">暂无 Skills</p>';
    return;
  }
  list.innerHTML = entries.map(s => `
    <div class="skill-item ${state.activeSkillId === s.id ? 'active' : ''}" data-id="${s.id}">
      <span class="skill-icon">${escHtml(s.icon)}</span>
      <div class="skill-info">
        <div class="skill-name">${escHtml(s.name)}</div>
        <div class="skill-desc">${escHtml(s.description)}</div>
      </div>
      <div class="skill-actions">
        <button title="编辑" onclick="event.stopPropagation();openSkillModal('${s.id}')">✏️</button>
        <button class="del-btn" title="删除" onclick="event.stopPropagation();deleteSkill('${s.id}')">🗑️</button>
      </div>
    </div>`).join('');

  list.querySelectorAll('.skill-item').forEach(el => {
    el.addEventListener('click', () => activateSkill(el.dataset.id));
  });
}

function activateSkill(id) {
  if (state.activeSkillId === id) {
    clearActiveSkill();
    return;
  }
  state.activeSkillId = id;
  const skill = state.skills[id];
  activeSkillBar.style.display = 'flex';
  activeSkillName.textContent = `${skill.icon} ${skill.name} 已激活`;
  promptHintEl.textContent = '⚡ Skill 已激活，System Prompt 将被 Skill Prompt 覆盖';
  renderSkills();
}

function clearActiveSkill() {
  state.activeSkillId = null;
  activeSkillBar.style.display = 'none';
  promptHintEl.textContent = '';
  renderSkills();
}

// ─── Skill Modal ───────────────────────────────────────────────────────────
function openSkillModal(skillId) {
  state.editingSkillId = skillId;
  $('skillModalTitle').textContent = skillId ? '编辑 Skill' : '新建 Skill';

  if (skillId && state.skills[skillId]) {
    const s = state.skills[skillId];
    $('skillIcon').value = s.icon;
    $('skillName').value = s.name;
    $('skillDesc').value = s.description;
    $('skillPrompt').value = s.prompt;
  } else {
    $('skillIcon').value = '🤖';
    $('skillName').value = '';
    $('skillDesc').value = '';
    $('skillPrompt').value = '';
  }
  $('skillModal').style.display = 'flex';
  setTimeout(() => $('skillName').focus(), 50);
}

function closeSkillModal() {
  $('skillModal').style.display = 'none';
  state.editingSkillId = null;
}

async function saveSkill() {
  const name = $('skillName').value.trim();
  const prompt = $('skillPrompt').value.trim();
  if (!name || !prompt) { alert('名称和 Prompt 不能为空'); return; }

  const payload = {
    name,
    description: $('skillDesc').value.trim() || name,
    prompt,
    icon: $('skillIcon').value.trim() || '🤖',
  };

  const btn = $('saveSkillBtn');
  btn.disabled = true;
  btn.textContent = '保存中…';

  try {
    let res;
    if (state.editingSkillId) {
      res = await fetch(`/api/skills/${state.editingSkillId}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });
    } else {
      res = await fetch('/api/skills', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });
    }
    if (!res.ok) throw new Error('Save failed');
    closeSkillModal();
    await loadSkills();
  } catch (e) {
    alert('保存失败: ' + e.message);
  } finally {
    btn.disabled = false;
    btn.textContent = '保存';
  }
}

async function deleteSkill(id) {
  if (!confirm(`确定删除 Skill「${state.skills[id]?.name}」？`)) return;
  if (state.activeSkillId === id) clearActiveSkill();
  await fetch(`/api/skills/${id}`, { method: 'DELETE' });
  await loadSkills();
}

// Close modal on overlay click
$('skillModal').addEventListener('click', e => {
  if (e.target === $('skillModal')) closeSkillModal();
});

// Expose for inline handlers
window.openSkillModal = openSkillModal;
window.deleteSkill = deleteSkill;
window.closeSkillModal = closeSkillModal;
window.saveSkill = saveSkill;
