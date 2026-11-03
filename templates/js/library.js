/* Saved media: private data stays on the local gallery server. */
(() => {
  'use strict';
  const base = '/galleryout/library/api/';
  const dialog = document.getElementById('sg-library');
  const grid = document.getElementById('sg-grid');
  const detail = document.getElementById('sg-detail');
  let record = null;
  let searchSequence = 0;
  let dirty = false;
  const message = text => { document.getElementById('sg-message').textContent = text; };
  const el = (tag, attrs = {}, text = '') => {
    const node = document.createElement(tag);
    for (const [key, value] of Object.entries(attrs)) {
      if (key === 'class') node.className = value;
      else if (key.startsWith('on')) node.addEventListener(key.slice(2), value);
      else if (key === 'value') node.value = value;
      else node.setAttribute(key, value);
    }
    if (text) node.textContent = text;
    return node;
  };
  async function api(path, method = 'GET', body) {
    const response = await fetch(base + path, {method, headers: {'Content-Type': 'application/json', 'X-SG-Library': '1'}, body: body === undefined ? undefined : JSON.stringify(body)});
    const data = await response.json();
    if (!response.ok) throw new Error(data.error || data.message || 'The request failed.');
    return data;
  }
  const attempt = fn => async (...args) => {
    try { await fn(...args); } catch (error) { message(error.message); }
  };
  function media(asset, className, controls = false) {
    const filename = asset.filename || asset.original.filename;
    const video = /\.(mp4|webm|mkv|mov|avi)$/i.test(filename);
    const audio = /\.(mp3|wav|flac|ogg)$/i.test(filename);
    const node = el(video ? 'video' : audio ? 'audio' : 'img', {class: className, src: base + `assets/${asset.id}/media`});
    if (video || audio) { node.preload = 'metadata'; node.controls = controls; node.muted = !controls; }
    else { node.alt = asset.title; node.loading = 'lazy'; }
    return node;
  }
  async function search() {
    const sequence = ++searchSequence;
    const data = await api('assets?q=' + encodeURIComponent(document.getElementById('sg-search').value));
    if (sequence !== searchSequence) return;
    grid.replaceChildren();
    document.getElementById('sg-count').textContent = `${data.total} asset${data.total === 1 ? '' : 's'}`;
    if (!data.items.length) {
      const empty = el('div', {class: 'sg-empty'});
      empty.append(el('div', {class: 'sg-empty-icon'}, '◇'), el('strong', {}, 'Your media library is ready.'), el('div', {}, 'Open an image or video and choose Add to Smart Media Manager.'), el('div', {}, 'Its original file and available workflow will be saved here.'));
      grid.append(empty);
    }
    const grouping = document.getElementById('sg-group').value;
    const groupKey = a => ['workflow', 'prompt'].includes(grouping) ? a.clustering?.[grouping] || '' : String(a[grouping] || '');
    if (grouping) data.items.sort((a, b) => groupKey(a).localeCompare(groupKey(b)));
    let lastGroup = null, groupNumber = 0;
    for (const asset of data.items) {
      const key = groupKey(asset);
      if (grouping && key !== lastGroup) {
        const heading = el('h3', {class: 'sg-group-heading'}, ['workflow', 'prompt'].includes(grouping) ? (key ? `${grouping === 'workflow' ? 'Workflow' : 'Prompt'} group ${++groupNumber}` : 'No embedded ' + grouping) : (key || 'Unsorted'));
        if (grouping === 'rating') heading.textContent = key ? '★'.repeat(Number(key)) : 'Unrated';
        grid.append(heading); lastGroup = key;
      }
      const card = el('article', {class: 'sg-card' + (record?.id === asset.id ? ' selected' : '')});
      const preview = el('button', {class: 'sg-card-open', onclick: attempt(() => openAsset(asset.id)), 'aria-label': 'Open ' + asset.title});
      const body = el('div', {class: 'sg-card-body'});
      const meta = el('small');
      meta.append(el('span', {}, asset.collection || 'Unsorted'), el('span', {}, asset.rating ? '★'.repeat(asset.rating) : asset.has_workflow ? 'Workflow saved' : 'No workflow saved'));
      body.append(el('strong', {}, asset.title), meta);
      preview.append(media(asset, ''), body);
      const actions = el('div', {class: 'sg-card-actions'});
      actions.append(workflowButton(asset, asset.has_workflow));
      card.append(preview, actions);
      grid.append(card);
    }
    if (data.total > data.items.length) grid.append(el('p', {class: 'sg-meta'}, 'Showing the latest 100 matches. Search to narrow the results.'));
  }
  function workflowButton(asset, available) {
    const button = el('button', {class: 'sg-button primary', onclick: attempt(() => loadWorkflow(asset))},
      window.parent !== window ? 'Load Workflow' : 'Download Workflow');
    button.disabled = !available;
    button.title = !available ? 'This asset has no saved UI workflow.'
      : window.parent !== window ? 'Load the saved graph into ComfyUI' : 'Download the saved workflow JSON';
    return button;
  }
  function field(parent, name, value, type = 'input') {
    const label = el('label', {}, name);
    const control = el(type, {value: value ?? ''});
    label.append(control); parent.append(label);
    control.addEventListener('input', () => { dirty = true; });
    return control;
  }
  async function openAsset(id, force = false) {
    if (dirty && !force && !confirm('Discard unsaved changes to this asset?')) return;
    record = await api('assets/' + id);
    dirty = false;
    detail.hidden = false;
    detail.replaceChildren();
    const heading = el('div', {class: 'sg-detail-heading'});
    heading.append(el('strong', {}, 'Asset details'), el('button', {class: 'sg-icon-button', 'aria-label': 'Close details', onclick: () => {
      if (dirty && !confirm('Discard unsaved changes?')) return;
      dirty = false; detail.hidden = true; record = null;
    }}, '×'));
    const controls = el('div', {class: 'sg-detail-controls'});
    controls.append(heading);
    const actions = el('div', {class: 'sg-actions'});
    const load = workflowButton(record, record.original.has_workflow);
    const original = el('a', {class: 'sg-button', href: base + `assets/${id}/media`, download: record.original.filename}, 'Original ↓');
    actions.append(load, original, el('button', {class: 'sg-button', onclick: attempt(async () => {
      const result = await api(`assets/${id}/verify`);
      message(result.ok ? `Verified ${result.files.length} archived files. ${result.unresolved_references.length} unresolved media references.` : 'Verification failed. An archived file is missing or changed.');
    })}, 'Verify files'));
    controls.append(actions, el('span', {class: 'sg-badge'}, record.original.has_workflow ? 'Full workflow saved' : 'No workflow saved'));
    if (!record.original.has_workflow) controls.append(el('p', {class: 'sg-meta'}, record.original.has_prompt
      ? 'Generation settings are saved, but this file does not contain a full UI workflow.'
      : 'This file has no saved workflow. Load Workflow is unavailable.'));
    detail.append(controls, media(record, 'sg-preview', true));
    detail.scrollTop = 0;
    const fields = el('div', {class: 'sg-fields'});
    const title = field(fields, 'Title', record.title);
    const row = el('div', {class: 'sg-field-row'}); fields.append(row);
    const collection = field(row, 'Collection', record.collection);
    const rating = field(row, 'Rating', '', 'select');
    for (let i = 0; i <= 5; i++) rating.append(el('option', {value: String(i)}, i ? '★'.repeat(i) : 'Unrated'));
    rating.value = String(record.rating || 0);
    const tags = field(fields, 'Tags · separate with commas', record.tags.join(', '));
    const notes = field(fields, 'Notes', record.notes, 'textarea');
    notes.placeholder = 'What worked, what to try next, and anything worth remembering…';
    const facts = el('div', {class: 'sg-facts'});
    const factInputs = [];
    function addFact(fact = {key: '', value: '', source_type: 'user'}) {
      const box = el('div', {class: 'sg-fact'});
      const key = el('input', {value: fact.key, placeholder: 'Fact · e.g. LoRA trigger', 'aria-label': 'Fact name'});
      const value = el('input', {value: fact.value, placeholder: 'Value', 'aria-label': 'Fact value'});
      const type = el('select', {'aria-label': 'Evidence type'});
      for (const [v, label] of Object.entries({user: 'User note', author: 'Author says', verified: 'Verified', inferred: 'Inferred'})) type.append(el('option', {value: v}, label));
      type.value = fact.source_type;
      const url = el('input', {value: fact.source_url || '', placeholder: 'Source URL (optional)', 'aria-label': 'Source URL'});
      const item = {fact, box, key, value, type, url}; factInputs.push(item);
      box.append(key, value, type, url, el('button', {class: 'sg-button', onclick: () => { box.remove(); dirty = true; }}, 'Remove fact'));
      box.addEventListener('input', () => { dirty = true; });
      facts.append(box);
    }
    const factTitle = el('div', {class: 'sg-section-title'});
    factTitle.append(el('strong', {}, 'Research & context'), el('button', {class: 'sg-button', onclick: () => { addFact(); dirty = true; }}, '+ Add fact'));
    fields.append(factTitle, el('p', {class: 'sg-meta'}, 'Keep researched information separate from the original generation data.'), facts);
    record.facts.forEach(addFact);
    const save = el('button', {class: 'sg-button primary', onclick: attempt(async () => {
      save.disabled = true;
      try {
        const updated = {title: title.value, collection: collection.value, rating: Number(rating.value) || null,
          tags: tags.value.split(',').map(x => x.trim()).filter(Boolean), notes: notes.value,
          facts: factInputs.filter(f => f.box.isConnected).map(f => ({...f.fact, key: f.key.value, value: f.value.value, source_type: f.type.value, source_url: f.url.value}))};
        await api('assets/' + id, 'PATCH', {expected_revision: record.revision, fields: updated, actor: 'user', reason: 'Edited in Smart Media Manager'});
        await openAsset(id, true); await search(); message('Saved. The original generation data is unchanged.');
      } finally { save.disabled = false; }
    })}, 'Save changes');
    fields.append(save); detail.append(fields);
    const history = el('details'); history.append(el('summary', {}, `History · ${record.history.length} revision${record.history.length === 1 ? '' : 's'}`));
    [...record.history].reverse().forEach(event => {
      const entry = el('div', {class: 'sg-history'});
      if (event.revision !== record.revision) entry.append(el('button', {class: 'sg-button', onclick: attempt(async () => {
        if (!confirm(`Restore metadata from revision ${event.revision}? Current metadata remains in history.`)) return;
        await api(`assets/${id}/restore`, 'POST', {revision: event.revision, expected_revision: record.revision, actor: 'user'});
        await openAsset(id, true); await search(); message('Metadata restored as a new revision.');
      })}, 'Restore'));
      entry.append(el('strong', {}, `v${event.revision} · ${event.actor}`), el('p', {}, event.reason), el('span', {}, new Date(event.at).toLocaleString()));
      history.append(entry);
    });
    detail.append(history, el('p', {class: 'sg-meta'}, `Original: ${record.original.filename}\nID: ${id}`));
    if (record.references.some(r => r.status !== 'copied')) detail.append(el('p', {class: 'sg-meta'}, 'Some media references could not be captured. Models and custom nodes must remain installed separately.'));
  }
  function downloadJson(value, name) {
    const url = URL.createObjectURL(new Blob([JSON.stringify(value, null, 2)], {type: 'application/json'}));
    const link = el('a', {href: url, download: name}); link.click(); setTimeout(() => URL.revokeObjectURL(url), 30000);
  }
  async function loadWorkflow(asset) {
    const result = await api(`assets/${asset.id}/prepare`, 'POST', {});
    if (window.parent !== window) {
      const parentOrigin = new URL(document.referrer).origin;
      if (!['localhost', '127.0.0.1', '[::1]'].includes(new URL(parentOrigin).hostname)) throw new Error('Open this gallery through the local ComfyUI sidebar.');
      window.parent.postMessage({type: 'smartgallery:load-workflow', workflow: result.workflow, title: asset.title}, parentOrigin);
      message('Workflow sent to ComfyUI. No generation was queued.');
    } else {
      downloadJson(result.workflow, asset.title.replace(/[<>:"/\\|?*]/g, '_') + '.json');
      message('Downloaded the full graph with captured media paths restored. Open it in ComfyUI.');
    }
    if (result.unresolved_references.length) message('Workflow opened with unresolved media references. Check its input nodes before running.');
  }
  async function open(id) {
    if (!dialog.open) dialog.showModal();
    message(''); await search();
    if (id) await openAsset(id);
  }
  window.SG = {
    open: attempt(open),
    keep: attempt(async fileId => {
      await open(); message('Copying the original and collecting its workflow…');
      const data = await api('assets', 'POST', {file_id: fileId, actor: 'user'});
      await search(); await openAsset(data.record.id);
      message(data.created ? 'Added to Smart Media Manager. This copy is independent of your output folder.' : 'This exact file is already in Smart Media Manager.');
    }),
    keepSelected: attempt(async ids => {
      await open(); let count = 0;
      for (const file_id of ids) { message(`Adding asset ${++count} of ${ids.length}…`); await api('assets', 'POST', {file_id, actor: 'user'}); }
      await search(); message(`${count} selected files are now in your library.`);
    })
  };
  document.getElementById('sg-close').onclick = () => { if (!dirty || confirm('Discard unsaved changes?')) { dirty = false; dialog.close(); } };
  dialog.addEventListener('cancel', event => { if (dirty && !confirm('Discard unsaved changes?')) event.preventDefault(); else dirty = false; });
  dialog.addEventListener('keydown', event => event.stopPropagation());
  let timer;
  document.getElementById('sg-search').addEventListener('input', () => { clearTimeout(timer); timer = setTimeout(attempt(search), 200); });
  document.getElementById('sg-group').addEventListener('change', attempt(search));
  const requested = new URLSearchParams(location.search).get('library');
  if (requested !== null) SG.open(requested || undefined);
})();
