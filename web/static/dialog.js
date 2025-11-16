// userId, ADMIN_NAME, messages приходят из dialog.html

const messagesDiv = document.getElementById('messages');
const input = document.getElementById('input');
const sendBtn = document.getElementById('send');
const clearBtn = document.getElementById('clearChat');
const status = document.getElementById('status');
const backBtn = document.getElementById('backBtn');
const attachBtn = document.getElementById('attachBtn');
const fileInput = document.getElementById('fileInput');
const previewArea = document.getElementById('previewArea');

let previewFiles = [];  // файлы, ожидающие отправки
let ws, reconnectTimer, pingInterval;

const WS_PATH =
  (location.protocol === "https:" ? "wss://" : "ws://") +
  location.host + "/ws/" + userId;

window._chatWs = null;

// ---------------- Helpers ------------------

function escapeHtml(s) {
  return s
    ? String(s)
        .replaceAll('&','&amp;')
        .replaceAll('<','&lt;')
        .replaceAll('>','&gt;')
        .replaceAll('"','&quot;')
    : '';
}

function formatTime(iso) {
  try {
    return new Date(iso).toLocaleString();
  } catch (e) {
    return iso;
  }
}

async function scrollBottom() {
  await new Promise(r => requestAnimationFrame(r));
  messagesDiv.scrollTop = messagesDiv.scrollHeight;
}

function getStatusIcon(status) {
  switch (status) {
    case "sent": return "🕐";
    case "delivered": return "✓";
    case "read": return "✅";
    case "deleted": return "🗑️";
    default: return "";
  }
}

// ---------------- Rendering ------------------

function renderAll() {
  messagesDiv.innerHTML = '';
  messages.sort((a,b)=> new Date(a.created_at) - new Date(b.created_at));
  for (const m of messages) renderOne(m);
  scrollBottom();
}

function renderOne(m) {
  const el = document.createElement('div');
  const isDeleted = m.status === "deleted";
  const adminName = (ADMIN_NAME || 'admin').toLowerCase();
  const isAdmin = ((m.username || '').toLowerCase() === adminName);

  el.className = 'msg ' + (isAdmin ? 'admin' : 'user') + (isDeleted ? ' deleted' : '');
  el.dataset.id = m.id;

  let content = escapeHtml(m.text || "").replaceAll("\n", "<br>");

  let mediaHtml = "";
  if (m.file_id) {
    const url = `/media_proxy/${encodeURIComponent(m.file_id)}`;

    if (m.media_type === "photo") {
      mediaHtml = `<img src="${url}" class="media-img">`;
    } else if (m.media_type === "video") {
      mediaHtml = `<video controls src="${url}" class="media-video"></video>`;
    } else if (m.media_type === "document") {
      mediaHtml = `<a href="${url}" target="_blank">📄 Скачать документ</a>`;
    } else if (m.media_type === "voice" || m.media_type === "audio") {
      mediaHtml = `<audio controls src="${url}" class="media-audio"></audio>`;
    }
  }

  el.innerHTML = `
    ${mediaHtml}
    <div class="text">${content}</div>
    <div class="meta">
      ${formatTime(m.created_at)}
      <span class="status-tag">${getStatusIcon(m.status)}</span>
    </div>
    <div class="delete-btn" title="Удалить">×</div>
  `;

  el.querySelector('.delete-btn').onclick = async () => {
    if (!confirm('Удалить это сообщение у пользователя?')) return;
    await deleteMessage(m.id);
  };

  messagesDiv.appendChild(el);
  scrollBottom();
}

// ---------------- WebSocket ------------------

function connectWS() {
  status.textContent = 'Подключение...';
  ws = new WebSocket(WS_PATH);
  window._chatWs = ws;

  ws.onopen = () => {
    status.textContent = 'Онлайн';
    ws.send(JSON.stringify({action:'ping'}));

    if (pingInterval) clearInterval(pingInterval);
    pingInterval = setInterval(() => {
      if (ws.readyState === WebSocket.OPEN)
        ws.send(JSON.stringify({action:'ping'}));
    }, 20000);
  };

  ws.onmessage = (ev) => {
    try {
      const data = JSON.parse(ev.data);

      if (data.action === 'message') {
        const msg = {
          id: data.id ?? Date.now(),
          username: data.username || (data.from === 'admin' ? ADMIN_NAME : 'user'),
          text: data.text || '',
          created_at: data.created_at || new Date().toISOString(),
          status: data.status || 'delivered',
          media_type: data.media_type || null,
          file_id: data.file_id || null
        };
        messages.push(msg);
        renderOne(msg);

      } else if (data.action === 'status_update') {
        const msg = messages.find(m => m.id === data.msg_id);
        if (msg) {
          msg.status = data.status;
          renderAll();
        }
      } else if (data.action === 'cleared') {
        messages = [];
        renderAll();
      }

    } catch (e) {
      console.error("WS error", e);
    }
  };

  ws.onclose = () => {
    status.textContent = 'Оффлайн — переподключение...';
    if (pingInterval) clearInterval(pingInterval);
    reconnectTimer = setTimeout(connectWS, 1500);
  };
}

// ---------------- Delete ------------------

async function deleteMessage(msgId) {
  const fd = new FormData();
  fd.append('user_id', userId);
  fd.append('msg_id', msgId);
  const res = await fetch('/delete_msg', {method:'POST', body: fd});
  const data = await res.json();

  if (data.ok) {
    const msg = messages.find(m => m.id === msgId);
    if (msg) msg.status = "deleted";
    renderAll();
  }
}

// ---------------- PREVIEW ------------------

function addPreview(files) {
  for (const f of files) {
    const id = crypto.randomUUID();
    const url = URL.createObjectURL(f);
    const isImage = f.type.startsWith("image/");

    const el = document.createElement("div");
    el.className = "preview-item";
    el.dataset.id = id;

    el.innerHTML = `
      ${isImage ? `<img src="${url}">` : `<div>${escapeHtml(f.name)}</div>`}
      <div class="preview-remove">×</div>
      <div class="preview-progress">Готово</div>
    `;

    el.querySelector(".preview-remove").onclick = () => {
      previewFiles = previewFiles.filter(x => x.id !== id);
      el.remove();
    };

    previewFiles.push({ id, file: f, el });
    previewArea.appendChild(el);
  }
}

// ---------------- Upload with progress ------------------

async function uploadFile(item) {
  return new Promise((resolve) => {
    const xhr = new XMLHttpRequest();
    const fd = new FormData();
    fd.append("user_id", userId);
    fd.append("files", item.file);

    const progressEl = item.el.querySelector(".preview-progress");

    xhr.upload.onprogress = (e) => {
      if (e.lengthComputable) {
        const pct = Math.round((e.loaded / e.total) * 100);
        progressEl.textContent = `${pct}%`;
      }
    };

    xhr.onload = () => {
      let data = {};
      try {
        data = JSON.parse(xhr.responseText);
      } catch {}

      if (data.ok && data.files?.length) {
        progressEl.textContent = "📤 Отправлено";
        resolve(true);
      } else {
        progressEl.textContent = "❌ Ошибка";
        resolve(false);
      }
    };

    xhr.onerror = () => {
      progressEl.textContent = "❌ Ошибка";
      resolve(false);
    };

    xhr.open("POST", "/upload_admin_file");
    xhr.send(fd);
  });
}

// ---------------- SEND ------------------

async function sendMessage() {
  const text = input.value.trim();

  // 1. Загрузить файлы
  for (const item of previewFiles) {
    await uploadFile(item);
    await new Promise(r => setTimeout(r, 120));
  }

  // очистить превью
  previewArea.innerHTML = "";
  previewFiles = [];

  // 2. Отправить текст
  if (text && ws.readyState === WebSocket.OPEN) {
    ws.send(JSON.stringify({ action: "send", text }));
  }

  input.value = "";
}

sendBtn.addEventListener('click', sendMessage);
input.addEventListener('keydown', (e)=>{
  if (e.ctrlKey && e.key === 'Enter') sendMessage();
});

// ---------------- Attach ------------------

attachBtn.addEventListener('click', ()=> fileInput.click());

fileInput.addEventListener('change', ()=> {
  if (fileInput.files.length) addPreview(fileInput.files);
  fileInput.value = "";
});

// ---------------- Drag & Drop ------------------

messagesDiv.addEventListener("dragover", e => {
  e.preventDefault();
  messagesDiv.classList.add("dragover");
});

messagesDiv.addEventListener("dragleave", () => {
  messagesDiv.classList.remove("dragover");
});

messagesDiv.addEventListener("drop", e => {
  e.preventDefault();
  messagesDiv.classList.remove("dragover");

  if (e.dataTransfer.files.length)
    addPreview(e.dataTransfer.files);
});

// ---------------- Clear ------------------

clearBtn.addEventListener('click', ()=> {
  if (!confirm('Удалить всю историю?')) return;
  ws.send(JSON.stringify({action:'clear_history'}));
});

// ---------------- Init ------------------

backBtn.addEventListener('click', ()=> window.location.href='/');
connectWS();
renderAll();
scrollBottom();
