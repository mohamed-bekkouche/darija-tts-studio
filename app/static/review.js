(() => {
  const clips = window.__CLIPS__ || [];
  const jobId = window.__JOB_ID__;
  const main = document.getElementById('review-main');
  const confButtons = document.querySelectorAll('.conf-btn');
  if (!main || !clips.length) return;

  let current = 0;

  const el = {
    list:         document.getElementById('clip-list'),
    title:        document.getElementById('clip-title'),
    badge:        document.getElementById('clip-status-badge'),
    audio:        document.getElementById('audio-player'),
    raw:          document.getElementById('text-raw'),
    precleaned:   document.getElementById('text-precleaned'),
    precleanedBlk:document.getElementById('precleaned-block'),
    normalized:   document.getElementById('text-normalized'),
    changes:      document.getElementById('changes-list'),
    changesBlk:   document.getElementById('changes-block'),
    uncertain:    document.getElementById('uncertain-words'),
    uncertainBlk: document.getElementById('uncertain-block'),
    finalBox:     document.getElementById('text-final'),
    prev:         document.getElementById('btn-prev'),
    next:         document.getElementById('btn-next'),
    accept:       document.getElementById('btn-accept'),
    reject:       document.getElementById('btn-reject'),
    skip:         document.getElementById('btn-skip'),
    revert:       document.getElementById('btn-revert'),
    progress:     document.getElementById('progress-label'),
    navPos:       document.getElementById('nav-position'),
    toolbar:      document.getElementById('filler-toolbar'),
    warnBlk:      document.getElementById('unmatched-warning'),
    warnList:     document.getElementById('unmatched-list'),
    dictPopup:    document.getElementById('dict-popup'),
    dictPhonetic: document.getElementById('dict-phonetic'),
    dictFrench:   document.getElementById('dict-french'),
    dictSave:     document.getElementById('dict-save'),
    dictSkip:     document.getElementById('dict-skip'),
  };

  function render() {
    const tr = clips[current];
    if (!tr) return;

    el.title.textContent = `Clip ${String(current+1).padStart(3,'0')} / ${String(clips.length).padStart(3,'0')}`;
    el.navPos.textContent = `${current+1} / ${clips.length}`;

    const status = tr.review_status || 'pending';
    el.badge.textContent = status;
    el.badge.className = 'state state-' + status;

    el.raw.textContent = tr.raw || '(empty)';

    // pre-cleaned layer
    if (tr.pre_cleaned && tr.pre_cleaned !== tr.raw) {
      el.precleaned.textContent = tr.pre_cleaned;
      el.precleanedBlk.style.display = '';
    } else {
      el.precleanedBlk.style.display = 'none';
    }

    el.normalized.textContent = tr.normalized || '(empty)';

    // unmatched French warning
    const unmatched = tr.unmatched_french || [];
    if (unmatched.length) {
      el.warnList.textContent = unmatched.join('  •  ');
      el.warnBlk.style.display = '';
    } else {
      el.warnBlk.style.display = 'none';
    }

    // changes
    const changes = tr.llm_changes || [];
    if (changes.length) {
      el.changes.innerHTML = '';
      for (const c of changes) {
        const li = document.createElement('li');
        li.textContent = `${c.from || '(start)'} → ${c.to || '(end)'}  [${c.type||''}]`;
        el.changes.appendChild(li);
      }
      el.changesBlk.style.display = '';
    } else {
      el.changesBlk.style.display = 'none';
    }

    // Highlight current confidence
    const currentConf = tr.review_confidence || 'accepted_quick';
    confButtons.forEach(b => {
      b.classList.toggle('active', b.dataset.conf === currentConf);
    });

    // uncertain
    const uncertain = tr.llm_uncertain || [];
    if (uncertain.length) {
      el.uncertain.textContent = uncertain.join('  •  ');
      el.uncertainBlk.style.display = '';
    } else {
      el.uncertainBlk.style.display = 'none';
    }

    el.finalBox.value = tr.final || tr.normalized || tr.raw || '';

    el.audio.src = `/jobs/${jobId}/clip/${tr.audio}`;
    el.audio.load();

    document.querySelectorAll('.clip-item').forEach((li, i) => {
      li.classList.toggle('active', i === current);
    });

    updateProgress();
  }

  function updateProgress() {
    const done = clips.filter(c => c.review_status && c.review_status !== 'pending').length;
    el.progress.textContent = `${done} / ${clips.length} reviewed`;
  }

  function syncSidebarStatus() {
    document.querySelectorAll('.clip-item').forEach((li, i) => {
      const st = clips[i].review_status || 'pending';
      li.dataset.status = st;
    });
  }

  async function saveClip(index, status) {
    const tr = clips[index];
    const newFinal = el.finalBox.value;
    const previousFinal = tr.final || tr.normalized || tr.raw || '';

    console.log('[save] start', { index, status, newFinal, previousFinal });

    const payload = {
      final: newFinal,
      review_status: status,
      review_confidence: tr.review_confidence || 'accepted_quick',
    };
    console.log('[save] POST payload', payload);

    let res;
    try {
      res = await fetch(`/api/jobs/${jobId}/clips/${index}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });
    } catch (err) {
      console.error('[save] network error', err);
      alert('Network error saving clip: ' + err.message);
      return;
    }

    console.log('[save] response status', res.status);

    if (!res.ok) {
      const errText = await res.text();
      console.error('[save] server error', res.status, errText);
      alert(`Save failed (${res.status}): ${errText}`);
      return;
    }

    const data = await res.json();
    console.log('[save] response data', data);

    tr.final = data.clip.final;
    tr.review_status = data.clip.review_status;
    syncSidebarStatus();
    updateProgress();

    if (status === 'accepted' && newFinal !== previousFinal) {
      console.log('[save] text changed — calling dict popup');
      maybeOfferDictionaryAdd(index, previousFinal, newFinal);
    } else {
      console.log('[save] no text change or not accepted — skipping popup');
    }
  }

  function go(index) {
    if (index < 0 || index >= clips.length) return;
    current = index;
    render();
  }

  async function accept() {
    await saveClip(current, 'accepted');
    if (current < clips.length - 1) go(current + 1);
  }

  async function reject() {
    await saveClip(current, 'rejected');
    if (current < clips.length - 1) go(current + 1);
  }

  async function skip() {
    await saveClip(current, 'skipped');
    if (current < clips.length - 1) go(current + 1);
  }

  function insertFiller(token) {
    const ta = el.finalBox;
    const start = ta.selectionStart;
    const end = ta.selectionEnd;
    const before = ta.value.slice(0, start);
    const after = ta.value.slice(end);
    const needsSpace = before.length && !before.endsWith(' ');
    const text = (needsSpace ? ' ' : '') + token + ' ';
    ta.value = before + text + after;
    const pos = (before + text).length;
    ta.setSelectionRange(pos, pos);
    ta.focus();
  }

  function maybeOfferDictionaryAdd(index, before, after) {
    console.log('[dict-popup] called');

    const cleanBefore = before.replace(/[\[\]]/g, '').trim();
    const cleanAfter  = after.replace(/[\[\]]/g, '').trim();

    if (cleanBefore === cleanAfter) {
      console.log('[dict-popup] no change');
      return;
    }

    // ── Character-level diff: find common prefix + suffix ──
    let prefixLen = 0;
    const minLen = Math.min(cleanBefore.length, cleanAfter.length);
    while (prefixLen < minLen &&
           cleanBefore[prefixLen] === cleanAfter[prefixLen]) {
      prefixLen++;
    }

    let suffixLen = 0;
    while (
      suffixLen < (minLen - prefixLen) &&
      cleanBefore[cleanBefore.length - 1 - suffixLen] ===
      cleanAfter[cleanAfter.length - 1 - suffixLen]
    ) {
      suffixLen++;
    }

    const beforeChanged = cleanBefore.slice(
      prefixLen,
      cleanBefore.length - suffixLen
    ).trim();

    const afterChanged = cleanAfter.slice(
      prefixLen,
      cleanAfter.length - suffixLen
    ).trim();

    console.log('[dict-popup] changed region:', {
      beforeChanged,
      afterChanged,
    });

    // ── Safety: skip if the change is too large ──────────
    // If more than ~6 words changed, it's not a single
    // French-phrase correction — skip the popup.
    const wordCount =
      beforeChanged.split(/\s+/).filter(Boolean).length +
      afterChanged.split(/\s+/).filter(Boolean).length;
    if (wordCount > 8) {
      console.log('[dict-popup] change too large (' + wordCount + ' words) — skipping');
      return;
    }

    // ── Extract Arabic phonetic candidate ────────────────
    const phonetic = beforeChanged.replace(/[،.؟!,;:]/g, '').trim();

    // ── Extract French candidate ─────────────────────────
    const french = afterChanged.replace(/[،.؟!,;:]/g, '').trim();

    // Both sides must contain the right script
    if (!phonetic || !/[\u0600-\u06FF]/.test(phonetic)) {
      console.log('[dict-popup] no Arabic in changed region');
      return;
    }
    if (!french || !/[a-zA-Z]/.test(french)) {
      console.log('[dict-popup] no Latin in changed region');
      return;
    }

    // Both sides should be short (safety again)
    if (phonetic.length > 60 || french.length > 60) {
      console.log('[dict-popup] changed region too long — skipping');
      return;
    }

    // ── Show the popup ────────────────────────────────────
    if (!el.dictPopup) {
      console.error('[dict-popup] popup element is NULL');
      return;
    }

    el.dictPhonetic.value = phonetic;
    el.dictFrench.value = french;
    el.dictPopup.style.display = 'flex';

    setTimeout(() => el.dictFrench.focus(), 50);
    console.log('[dict-popup] SHOWN with', { phonetic, french });

    el.dictSave.onclick = async () => {
      const payload = {
        phonetic: el.dictPhonetic.value.trim(),
        french: el.dictFrench.value.trim(),
      };
      if (!payload.phonetic || !payload.french) {
        alert('Both fields are required');
        return;
      }
      console.log('[dict-popup] saving', payload);
      try {
        const res = await fetch(`/api/jobs/${jobId}/dictionary`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(payload),
        });
        const data = await res.json();
        console.log('[dict-popup] save response', data);
      } catch (err) {
        console.error('[dict-popup] save error', err);
      }
      el.dictPopup.style.display = 'none';
    };
    el.dictSkip.onclick = () => {
      console.log('[dict-popup] skipped');
      el.dictPopup.style.display = 'none';
    };

    el.dictFrench.onkeydown = (e) => {
      if (e.key === 'Enter') {
        e.preventDefault();
        el.dictSave.click();
      }
    };
    el.dictPhonetic.onkeydown = (e) => {
      if (e.key === 'Enter') {
        e.preventDefault();
        el.dictFrench.focus();
      }
    };

    
  }

  el.list?.addEventListener('click', (e) => {
    const li = e.target.closest('.clip-item');
    if (!li) return;
    go(parseInt(li.dataset.index, 10));
  });

    confButtons.forEach(btn => {
    btn.addEventListener('click', async () => {
      const tr = clips[current];
      tr.review_confidence = btn.dataset.conf;
      confButtons.forEach(b => b.classList.toggle('active', b === btn));
      // Save immediately
      await fetch(`/api/jobs/${jobId}/clips/${current}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ review_confidence: btn.dataset.conf }),
      });
    });
  });

  el.prev.addEventListener('click', () => go(current - 1));
  el.next.addEventListener('click', () => go(current + 1));
  el.accept.addEventListener('click', accept);
  el.reject.addEventListener('click', reject);
  el.skip.addEventListener('click', skip);
  el.revert.addEventListener('click', () => {
    el.finalBox.value = clips[current].normalized || clips[current].raw || '';
  });

  el.toolbar?.addEventListener('click', (e) => {
    const btn = e.target.closest('.filler-btn');
    if (!btn) return;
    insertFiller(btn.dataset.token);
  });

  document.addEventListener('keydown', (e) => {
    if (e.target === el.finalBox) {
      if (e.key === 'Escape') el.finalBox.blur();
      return;
    }
    if (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA') return;

    if (e.code === 'Space') { e.preventDefault(); el.audio.paused ? el.audio.play() : el.audio.pause(); }
    else if (e.key === 'Enter') { e.preventDefault(); accept(); }
    else if (e.key === 'x' || e.key === 'X') { e.preventDefault(); reject(); }
    else if (e.key === 'ArrowLeft') { e.preventDefault(); go(current - 1); }
    else if (e.key === 'ArrowRight') { e.preventDefault(); go(current + 1); }
    else if (e.key === 'e' || e.key === 'E') { e.preventDefault(); el.finalBox.focus(); }
  });

  syncSidebarStatus();
  render();
})();