// userId, ADMIN_NAME, messages приходят из dialog.html

const chatRoot = document.querySelector('.chat');
const messagesDiv = document.getElementById('messages');
const input = document.getElementById('input');
const sendBtn = document.getElementById('send');
const clearBtn = document.getElementById('clearChat');
const status = document.getElementById('status');
const backBtn = document.getElementById('backBtn');
const attachBtn = document.getElementById('attachBtn');
const fileInput = document.getElementById('fileInput');
const previewArea = document.getElementById('previewArea');

const MAX_ALBUM_ITEMS = 10;
let previewFiles = [];  // файлы, ожидающие отправки
let ws, reconnectTimer, pingInterval;
let sending = false;
let dragDepth = 0;

const WS_PATH =
  (location.protocol === "https:" ? "wss://" : "ws://") +
  location.host + "/ws/" + userId;

window._chatWs = null;

// ---------------- Helpers ------------------

function escapeHtml(s) {
  if (!s) return '';
  return String(s)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
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

  let content = escapeHtml(m.text || "").replace(/\n/g, "<br>");

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

function isAlbumFile(file) {
  return !!file && (file.type.startsWith('image/') || file.type.startsWith('video/'));
}

<<<<<<< ours
function addPreview(files) {
  for (const f of files) {
    if (!f) continue;
    const id = crypto.randomUUID();
=======
function addPreview(fileList) {
  const files = normalizeFiles(fileList);
  for (const f of files) {
    if (!f) continue;
    const id = makePreviewId();
>>>>>>> theirs
    const url = URL.createObjectURL(f);
    const isMedia = f.type.startsWith("image/") || f.type.startsWith("video/");

    const el = document.createElement("div");
    el.className = "preview-item";
    el.dataset.id = id;

    el.innerHTML = `
      ${isMedia ? `<img src="${url}" alt="preview">` : `<div class="preview-filename">${escapeHtml(f.name || 'файл')}</div>`}
      <div class="preview-remove">×</div>
      <div class="preview-progress">Ожидание</div>
    `;

    el.querySelector(".preview-remove").onclick = () => {
      previewFiles = previewFiles.filter(x => x.id !== id);
      URL.revokeObjectURL(url);
      el.remove();
      refreshPreviewArea();
    };

    previewFiles.push({ id, file: f, el, url });
    previewArea.appendChild(el);
  }
}

<<<<<<< ours
=======
function normalizeFiles(list) {
  if (!list) return [];
  if (Array.isArray(list)) return list.filter(Boolean);
  if (typeof FileList !== 'undefined' && list instanceof FileList) {
    return Array.from(list).filter(Boolean);
  }
  // DataTransferItemList or other iterable
  const out = [];
  if (typeof DataTransferItemList !== 'undefined' && list instanceof DataTransferItemList) {
    for (const item of list) {
      if (item && item.kind === 'file') {
        const file = item.getAsFile();
        if (file) out.push(file);
      }
    }
    return out;
  }
  try {
    for (const entry of list) {
      if (!entry) continue;
      if (typeof File !== 'undefined' && entry instanceof File) out.push(entry);
      else if (entry.getAsFile) {
        const file = entry.getAsFile();
        if (file) out.push(file);
      }
    }
  } catch (err) {
    console.warn('Cannot normalize files', err);
  }
  return out;
}

>>>>>>> theirs
function setPreviewStatus(item, text, state) {
  const progressEl = item.el.querySelector('.preview-progress');
  progressEl.textContent = text;
  progressEl.classList.remove('error', 'done');
  if (state === 'error') progressEl.classList.add('error');
  else if (state === 'done') progressEl.classList.add('done');
}

// ---------------- Upload with progress ------------------

function splitUploadGroups(queue) {
  const groups = [];
  let albumBuffer = [];

  const flushAlbum = () => {
    if (albumBuffer.length > 1) {
      groups.push([...albumBuffer]);
    } else if (albumBuffer.length === 1) {
      groups.push([albumBuffer[0]]);
    }
    albumBuffer = [];
  };

  for (const item of queue) {
    if (isAlbumFile(item.file)) {
      albumBuffer.push(item);
      if (albumBuffer.length === MAX_ALBUM_ITEMS) {
        groups.push([...albumBuffer]);
        albumBuffer = [];
      }
    } else {
      flushAlbum();
      groups.push([item]);
    }
  }

  flushAlbum();
  return groups;
}

async function uploadBatch(items) {
  return new Promise((resolve) => {
    const xhr = new XMLHttpRequest();
    const fd = new FormData();
    fd.append("user_id", userId);
    const isAlbum = items.length > 1 && items.every(it => isAlbumFile(it.file));
    if (isAlbum) {
      fd.append('album', '1');
    }

    items.forEach(item => {
      fd.append("files", item.file);
      setPreviewStatus(item, '0%', null);
    });

    xhr.upload.onprogress = (e) => {
      if (e.lengthComputable) {
        const pct = Math.round((e.loaded / e.total) * 100);
        items.forEach(item => {
          const progressEl = item.el.querySelector('.preview-progress');
          progressEl.textContent = `${pct}%`;
        });
      }
    };

    xhr.onload = () => {
      let data = {};
      try {
        data = JSON.parse(xhr.responseText);
      } catch {}

      if (data.ok && data.files?.length) {
        items.forEach(item => {
          item.uploaded = true;
          setPreviewStatus(item, "Отправлено", "done");
          setTimeout(() => {
            if (item.url) URL.revokeObjectURL(item.url);
            item.el.remove();
<<<<<<< ours
          }, 500);
        });
=======
            refreshPreviewArea();
          }, 500);
        });

        try {
          data.files.forEach((meta, idx) => {
            const message = {
              id: meta.msg_id ?? Date.now() + idx,
              username: ADMIN_NAME,
              text: '',
              created_at: meta.created_at || new Date().toISOString(),
              status: meta.status || 'delivered',
              media_type: meta.type || null,
              file_id: meta.id || null,
            };
            if (message.file_id) {
              messages.push(message);
              renderOne(message);
            }
          });
        } catch (err) {
          console.error('Cannot render uploaded files', err);
        }
>>>>>>> theirs
        resolve(true);
      } else {
        items.forEach(item => setPreviewStatus(item, "Ошибка", "error"));
        resolve(false);
      }
    };

    xhr.onerror = () => {
      items.forEach(item => setPreviewStatus(item, "Ошибка", "error"));
      resolve(false);
    };

    xhr.open("POST", "/upload_admin_file");
    xhr.send(fd);
  });
}

// ---------------- SEND ------------------

async function sendMessage() {
  if (sending) return;
  const text = input.value.trim();
  if (!text && previewFiles.length === 0) return;

  sending = true;
  sendBtn.disabled = true;

  try {
    // 1. Загрузить файлы
    const queue = [...previewFiles];
    const groups = splitUploadGroups(queue);
    for (const group of groups) {
      await uploadBatch(group);
      await new Promise(r => setTimeout(r, 120));
    }

    previewFiles = previewFiles.filter(item => !item.uploaded && item.el.isConnected);
    if (previewFiles.length === 0) {
      previewArea.innerHTML = '';
    }
<<<<<<< ours

    // 2. Отправить текст
    if (text && ws.readyState === WebSocket.OPEN) {
      ws.send(JSON.stringify({ action: "send", text }));
    }

=======

    // 2. Отправить текст
    if (text && ws.readyState === WebSocket.OPEN) {
      ws.send(JSON.stringify({ action: "send", text }));
    }

>>>>>>> theirs
    input.value = "";
  } finally {
    sending = false;
    sendBtn.disabled = false;
  }
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

function allowFileDrop(e) {
  if (!e.dataTransfer) return false;
  return Array.from(e.dataTransfer.types || []).includes('Files');
}

function highlightDropZone() {
  messagesDiv.classList.add('dragover');
  chatRoot?.classList.add('dragover');
}

function clearDropZone() {
  messagesDiv.classList.remove('dragover');
  chatRoot?.classList.remove('dragover');
}

document.addEventListener('dragenter', (e) => {
  if (!allowFileDrop(e)) return;
  dragDepth += 1;
  highlightDropZone();
});

document.addEventListener('dragover', (e) => {
  if (!allowFileDrop(e)) return;
  e.preventDefault();
  highlightDropZone();
});

document.addEventListener('dragleave', (e) => {
  if (!allowFileDrop(e)) return;
  dragDepth = Math.max(0, dragDepth - 1);
  if (dragDepth === 0) clearDropZone();
});

document.addEventListener('drop', (e) => {
  if (!allowFileDrop(e)) return;
  e.preventDefault();
  dragDepth = 0;
  clearDropZone();
  if (e.dataTransfer.files?.length) {
    addPreview(e.dataTransfer.files);
<<<<<<< ours
  }
=======
  } else if (e.dataTransfer.items?.length) {
    addPreview(e.dataTransfer.items);
  }
});

document.addEventListener('paste', (e) => {
  const clipboard = e.clipboardData || window.clipboardData;
  if (!clipboard) return;
  const files = normalizeFiles(clipboard.items || clipboard.files);
  if (!files.length) return;
  e.preventDefault();
  addPreview(files);
>>>>>>> theirs
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
function makePreviewId() {
  if (window.crypto && typeof window.crypto.randomUUID === 'function') {
    return window.crypto.randomUUID();
  }
  return 'file-' + Date.now().toString(36) + '-' + Math.random().toString(16).slice(2);
}

function refreshPreviewArea() {
  if (!previewArea.childElementCount) {
    previewArea.innerHTML = '';
  }
}

