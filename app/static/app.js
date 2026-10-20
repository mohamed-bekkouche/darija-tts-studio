// ---------- Upload page ----------
const dropzone = document.getElementById('dropzone');
const fileInput = document.getElementById('file-input');
const filenameEl = document.getElementById('filename');
const speakerInput = document.getElementById('speaker-input');
const submitBtn = document.getElementById('submit-btn');
const form = document.getElementById('upload-form');
const uploadMsg = document.getElementById('upload-msg');

let selectedFile = null;

function refreshSubmit() {
  submitBtn.disabled = !(selectedFile && speakerInput.value.trim());
}

if (dropzone) {
  dropzone.addEventListener('click', () => fileInput.click());

  ['dragenter', 'dragover'].forEach(ev =>
    dropzone.addEventListener(ev, e => {
      e.preventDefault(); dropzone.classList.add('dragover');
    }));
  ['dragleave', 'drop'].forEach(ev =>
    dropzone.addEventListener(ev, e => {
      e.preventDefault(); dropzone.classList.remove('dragover');
    }));

  dropzone.addEventListener('drop', e => {
    const f = e.dataTransfer.files[0];
    if (f) setFile(f);
  });

  fileInput.addEventListener('change', () => {
    if (fileInput.files[0]) setFile(fileInput.files[0]);
  });

  speakerInput.addEventListener('input', refreshSubmit);
}

function setFile(f) {
  selectedFile = f;
  filenameEl.textContent = f.name + ' (' + (f.size / 1e6).toFixed(1) + ' MB)';
  refreshSubmit();
}

if (form) {
  form.addEventListener('submit', async (e) => {
    e.preventDefault();
    if (!selectedFile) return;
    submitBtn.disabled = true;
    uploadMsg.textContent = 'Uploading…';

    const fd = new FormData();
    fd.append('file', selectedFile);
    fd.append('speaker', speakerInput.value.trim());

    try {
      const res = await fetch('/upload', { method: 'POST', body: fd });
      if (!res.ok) throw new Error(await res.text());
      const data = await res.json();
      uploadMsg.textContent = 'Done. Redirecting…';
      window.location.href = data.redirect;
    } catch (err) {
      uploadMsg.textContent = 'Error: ' + err.message;
      submitBtn.disabled = false;
    }
  });
}

// ---------- Job detail page ----------
const progressBar = document.getElementById('progress-bar');
const progressText = document.getElementById('progress-text');
const messageEl = document.getElementById('message');
const logsEl = document.getElementById('logs');
const stateBadge = document.getElementById('state-badge');

const jobRoot = document.getElementById('job-root');
const JOB_ID = jobRoot ? jobRoot.dataset.jobId : null;

if (progressBar && JOB_ID) {
  let stopped = false;

  async function poll() {
    if (stopped) return;
    try {
      const [jobRes, logRes] = await Promise.all([
        fetch('/api/jobs/' + JOB_ID),
        fetch('/api/jobs/' + JOB_ID + '/logs'),
      ]);
      if (jobRes.ok) {
        const j = await jobRes.json();
        const pct = (j.progress * 100).toFixed(1);
        progressBar.style.width = pct + '%';
        progressText.textContent = pct + '%';
        messageEl.textContent = j.message || '';
        stateBadge.textContent = j.state;
        stateBadge.className = 'state state-' + j.state;

        if (j.state === 'ready_for_review' || j.state === 'failed') {
          stopped = true;
          return;
        }
      }
      if (logRes.ok) {
        const text = await logRes.text();
        const atBottom = logsEl.scrollTop + logsEl.clientHeight >= logsEl.scrollHeight - 20;
        logsEl.textContent = text || '(no logs yet)';
        if (atBottom) logsEl.scrollTop = logsEl.scrollHeight;
      }
    } catch (err) {
      // silent, we'll retry
    }
    setTimeout(poll, 1500);
  }
  poll();
}