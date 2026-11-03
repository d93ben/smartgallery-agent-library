import { api } from '../../scripts/api.js';

export function installAssetMenu(app) {
  let pendingCard = null;
  const saving = new Set();
  const toast = options => app.extensionManager.toast.add({...options, life: 6500});

  async function keep(assetId) {
    if (saving.has(assetId)) return;
    saving.add(assetId);
    toast({severity: 'info', summary: 'Adding to Media Library…'});
    try {
      const response = await api.fetchApi('/smartgallery/library/keep', {
        method: 'POST', headers: {'Content-Type': 'application/json', 'X-SG-Library': '1'},
        body: JSON.stringify({asset_id: assetId})
      });
      if (!response.headers.get('content-type')?.includes('application/json')) {
        throw new Error(response.status === 404 ? 'Restart ComfyUI to enable the Media Library menu, then try again.' : 'ComfyUI could not save this asset. Try again.');
      }
      const result = await response.json();
      if (!response.ok) throw new Error(result.error || 'Could not add this asset.');
      toast({severity: 'success', summary: result.created ? 'Added to Media Library' : 'Already in Media Library',
        detail: result.title + ' · independent keeper copy'});
    } catch (error) {
      toast({severity: 'error', summary: 'Could not add to Media Library', detail: error.message});
    } finally {
      saving.delete(assetId);
    }
  }

  // ComfyUI's MediaAssetContextMenu currently has no extension hook. Match its
  // card's public data attribute and rendered PrimeVue menu, without Vue internals.
  function capture(event) {
    if (event.target.closest('[data-sg-keep]')) return;
    if (event.type === 'click' && !event.target.closest('button')) return;
    pendingCard = event.target.closest('[data-asset-id]');
    document.querySelectorAll('[data-sg-keep]').forEach(item => item.remove());
  }
  document.addEventListener('contextmenu', capture, true);
  document.addEventListener('click', capture, true);

  function addItem(menu) {
    if (!pendingCard || menu.querySelector('[data-sg-keep]')) return;
    const assetId = pendingCard.dataset.assetId;
    if (!assetId) return;
    const sample = menu.querySelector('[role="menuitem"]');
    if (!sample || sample.getAttribute('aria-disabled') === 'true') return; // Bulk menu.
    const item = sample.cloneNode(true);
    item.querySelectorAll('[id]').forEach(node => node.removeAttribute('id'));
    item.id = 'sg-keep-menu-item';
    item.dataset.sgKeep = '';
    item.setAttribute('aria-label', 'Add to Media Library');
    item.removeAttribute('data-p-focused');
    const action = item.querySelector('button, a');
    if (!action) return;
    action.replaceChildren();
    action.tabIndex = 0;
    const icon = document.createElement('i'); icon.className = 'sg-sidebar-icon'; icon.setAttribute('aria-hidden', 'true');
    const label = document.createElement('span'); label.textContent = 'Add to Media Library';
    action.append(icon, label);
    action.addEventListener('click', event => {
      event.preventDefault(); event.stopPropagation();
      pendingCard = null;
      action.dispatchEvent(new KeyboardEvent('keydown', {key: 'Escape', code: 'Escape', bubbles: true}));
      void keep(assetId);
    });
    action.addEventListener('keydown', event => {
      if (event.key === 'Enter' || event.key === ' ') {
        event.preventDefault(); event.stopPropagation(); action.click();
      }
    });
    sample.parentElement.insertBefore(item, sample);
    const items = [...menu.querySelectorAll('[role="menuitem"]')];
    items.forEach((entry, index) => {
      entry.setAttribute('aria-setsize', String(items.length));
      entry.setAttribute('aria-posinset', String(index + 1));
    });
    // Include the added entry in keyboard navigation; PrimeVue's internal
    // model otherwise skips items supplied by extensions.
    menu.addEventListener('keydown', event => {
      if (!['ArrowDown', 'ArrowUp', 'Home', 'End', 'Enter', ' '].includes(event.key)) return;
      const entries = [...menu.querySelectorAll('[role="menuitem"]')].filter(entry => entry.getAttribute('aria-disabled') !== 'true');
      const active = document.activeElement.closest('[role="menuitem"]') || document.getElementById(menu.getAttribute('aria-activedescendant'));
      const index = entries.indexOf(active);
      event.preventDefault(); event.stopPropagation();
      if (event.key === 'Enter' || event.key === ' ') {
        (entries[Math.max(index, 0)]?.querySelector('button, a'))?.click();
        return;
      }
      const next = event.key === 'Home' ? 0 : event.key === 'End' ? entries.length - 1
        : (index + (event.key === 'ArrowUp' ? -1 : 1) + entries.length) % entries.length;
      entries[next]?.querySelector('button, a')?.focus();
    }, true);
  }
  new MutationObserver(() => {
    if (pendingCard) document.querySelectorAll('.p-contextmenu-root-list').forEach(addItem);
  }).observe(document.body, {childList: true, subtree: true});
}
