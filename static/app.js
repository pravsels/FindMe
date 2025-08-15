
(() => {
    const fileInput   = document.getElementById('file');
    const drop        = document.getElementById('drop');
    const previewWrap = document.getElementById('preview');
    const facePreview = document.getElementById('facePreview');
    const forumInput  = document.getElementById('forum');
    const searchBtn   = document.getElementById('searchBtn');
    const cancelBtn   = document.getElementById('cancelBtn');
    const progressEl  = document.getElementById('progress');
    const results     = document.getElementById('results');
    const resultsHdr  = document.getElementById('resultsHeader');
  
    let currentJob = null;
    let es = null;
  
    // helpers
    const hueColor = (pct) => {
      const p = Math.max(0, Math.min(100, pct)) / 100;
      const hue = 120 * p; // 0=red, 120=green
      return `hsl(${hue}deg 80% 45%)`;
    };
    const setProgress = (msg) => { progressEl.textContent = msg || ''; };
  
    // keep list sorted by raw (desc)
    function insertSorted(node, raw) {
      const kids = Array.from(results.children);
      for (let i = 0; i < kids.length; i++) {
        const r = parseFloat(kids[i].dataset.raw || '-Infinity');
        if (raw > r) { results.insertBefore(node, kids[i]); return; }
      }
      results.appendChild(node);
    }
  
    function appendCandidate(c) {
      const card = document.createElement('div');
      card.className = 'rowcard';
      const raw = Number(c.score_raw ?? 0);
      card.dataset.raw = String(raw);
  
      const img = document.createElement('img');
      img.className = 'face';
      img.src = c.thumb;
      img.alt = 'Candidate face';
      
      const pctVal = Math.round(c.score_pct ?? 0);
      const bar = document.createElement('div');
      bar.className = 'bar';
      const fill = document.createElement('span');
      fill.style.background = hueColor(pctVal);
      bar.appendChild(fill);
  
      const pct = document.createElement('div');
      pct.className = 'pct';
      pct.style.fontWeight = '800';
      pct.style.fontSize = '12px';
      pct.style.marginTop = '6px';
      pct.textContent = `${pctVal}%`;
  
      const title = document.createElement('div');
      title.className = 'title';
      const a = document.createElement('a');
      a.href = c.post_url;
      a.target = '_blank';
      a.rel = 'noopener';
      a.textContent = c.title || '(no title)';
      title.appendChild(a);
  
      const meta = document.createElement('div');
      meta.className = 'meta';
      try {
        meta.textContent = `${new URL(c.post_url).host}${c.date ? ' • ' + c.date : ''}`;
      } catch {
        meta.textContent = `${c.date ? c.date : ''}`;
      }
  
      const middle = document.createElement('div');
      middle.appendChild(bar);
      middle.appendChild(pct);
      middle.appendChild(title);
      middle.appendChild(meta);
  
      card.appendChild(img);
      card.appendChild(middle);
  
      // animate bar fill after layout
      requestAnimationFrame(() => { fill.style.width = `${pctVal}%`; });
  
      insertSorted(card, raw);
    }
  
    // drag & drop
    drop.addEventListener('dragover', (e) => { e.preventDefault(); drop.style.borderColor = '#7aa2ff'; });
    drop.addEventListener('dragleave', () => { drop.style.borderColor = '#2a3350'; });
    drop.addEventListener('drop', (e) => {
      e.preventDefault(); drop.style.borderColor = '#2a3350';
      if (e.dataTransfer.files && e.dataTransfer.files[0]) {
        fileInput.files = e.dataTransfer.files;
        onFileChosen();
      }
    });
    drop.addEventListener('click', () => fileInput.click());
    fileInput.addEventListener('change', onFileChosen);
  
    function onFileChosen() {
      const f = fileInput.files && fileInput.files[0];
      if (!f) return;
      const reader = new FileReader();
      reader.onload = () => {
        previewWrap.classList.remove('hidden');
        facePreview.src = reader.result;
        searchBtn.disabled = false;
      };
      reader.readAsDataURL(f);
    }
  
    // search
    searchBtn.addEventListener('click', async () => {
      if (!fileInput.files || !fileInput.files[0]) { alert('Choose an image first.'); return; }
      const forum = forumInput.value.trim();
      if (!forum) { alert('Paste a reddit link.'); return; }
  
      // reset UI
      results.innerHTML = '';
      resultsHdr.textContent = 'Possible matches';
      setProgress('Starting…');
      cancelBtn.disabled = false;
      searchBtn.disabled = true;
  
      // start job
      const fd = new FormData();
      fd.append('photo', fileInput.files[0]);
      fd.append('forum_url', forum);
  
      let job_id;
      try {
        const res = await fetch('/api/analyze', { method: 'POST', body: fd });
        if (!res.ok) throw new Error(await res.text());
        job_id = (await res.json()).job_id;
        currentJob = job_id;
      } catch (err) {
        setProgress('Failed to start: ' + err);
        cancelBtn.disabled = true;
        searchBtn.disabled = false;
        return;
      }
  
      if (es) es.close();
      es = new EventSource(`/api/stream/${job_id}`);
  
      es.onmessage = (ev) => {
        if (!ev.data) return;
        const msg = JSON.parse(ev.data);
  
        if (msg.type === 'status') {
          setProgress(msg.text || '');
        } else if (msg.type === 'face') {
          previewWrap.classList.remove('hidden');
          facePreview.src = msg.thumb;
        } else if (msg.type === 'candidate') {
          appendCandidate(msg);
        } else if (msg.type === 'finalize') {
          setProgress(`Found ${msg.count || 0} candidates.`);
          cancelBtn.disabled = true;
          searchBtn.disabled = false;
          if (es) { es.close(); es = null; }
          currentJob = null;
        }
      };
  
      es.onerror = () => {
        setProgress('Connection closed.');
      };
    });
  
    // cancel
    cancelBtn.addEventListener('click', async () => {
      if (!currentJob) return;
      try { await fetch(`/api/cancel/${currentJob}`, { method: 'POST' }); } catch {}
      if (es) { es.close(); es = null; }
      setProgress('Cancel requested…');
      cancelBtn.disabled = true;
      searchBtn.disabled = false;
      currentJob = null;
    });
  })();

