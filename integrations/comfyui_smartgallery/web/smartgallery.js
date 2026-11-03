import { app } from '../../scripts/app.js';
import { installAssetMenu } from './asset-menu.js';

const icon = `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24"><g fill="none" stroke="black" stroke-width="1.8" stroke-linejoin="round"><path d="M5 5h14v14H5z"/><path d="m5 16 5-5 4 4 2-2 3 3M8 2h13a1 1 0 0 1 1 1v13"/><circle cx="15.5" cy="8.5" r="1"/></g></svg>`;
let frame, container;

app.registerExtension({
  name: 'SmartGallery.Library',
  settings: [{id: 'SmartGallery.URL', name: 'SmartGallery local address', type: 'text', defaultValue: 'http://127.0.0.1:8189'}],
  async setup() {
    const style = document.createElement('style');
    style.textContent = `.sg-sidebar-icon{display:inline-block;width:1.25rem;height:1.25rem;background:currentColor;mask:url("data:image/svg+xml,${encodeURIComponent(icon)}") center/contain no-repeat}.sg-comfy-panel{height:100%;min-height:0;display:flex;flex-direction:column;background:#111117}.sg-comfy-panel.sg-expanded{position:fixed;inset:30px 30px 30px 75px;height:auto;z-index:10000;border:1px solid #666;border-radius:12px;overflow:hidden;box-shadow:0 20px 80px #000a}.sg-comfy-bar{display:flex;gap:6px;padding:9px;flex-wrap:wrap;align-items:center}.sg-comfy-bar strong{font-size:12px;color:#d8caff;margin-right:auto}.sg-comfy-bar button,.sg-comfy-bar a{font:11px system-ui;background:#ffffff0e;color:#eee;border:1px solid #ffffff20;border-radius:6px;padding:6px 8px;cursor:pointer;text-decoration:none}.sg-comfy-panel iframe{border:0;flex:1;width:100%;min-height:0}.sg-comfy-help{font:11px system-ui;color:#aaa;padding:0 10px 8px}.sg-comfy-error{padding:16px;color:#ffb3b3;font:13px system-ui}`;
    document.head.append(style);
    installAssetMenu(app);
    function galleryUrl() {
      const url = new URL(app.ui.settings.getSettingValue('SmartGallery.URL', 'http://127.0.0.1:8189'));
      if (url.protocol !== 'http:' || !['localhost', '127.0.0.1', '[::1]'].includes(url.hostname)) throw new Error('Set a local HTTP gallery address in SmartGallery settings.');
      return url.origin;
    }
    function collapse() {
      container?.classList.remove('sg-expanded');
      const button = container?.querySelector('[data-expand]');
      if (button) button.textContent = 'Expand';
    }
    window.addEventListener('message', async event => {
      if (!frame || event.source !== frame.contentWindow || event.origin !== new URL(frame.src).origin || event.data?.type !== 'smartgallery:load-workflow') return;
      if (!Array.isArray(event.data.workflow?.nodes)) return;
      try {
        // A name creates a separate workflow tab through ComfyUI's normal loader.
        const name = 'Keeper - ' + String(event.data.title || 'Workflow').replace(/[<>:"/\\|?*]/g, '_');
        const loaded = await app.loadGraphData(event.data.workflow, true, true, name);
        if (loaded === false) throw new Error('ComfyUI could not load this graph. Check its workflow error dialog.');
        collapse();
      } catch (error) {
        app.extensionManager.toast.add({severity: 'error', summary: 'Could not open keeper workflow', detail: String(error), life: 8000});
      }
    });
    app.extensionManager.registerSidebarTab({
      id: 'smartgallery-library', icon: 'sg-sidebar-icon', title: 'SmartGallery', tooltip: 'SmartGallery · outputs and permanent keepers', type: 'custom',
      render(element) {
        element.style.height = '100%';
        if (container) { if (container.parentElement !== element) element.append(container); return; }
        container = document.createElement('div'); container.className = 'sg-comfy-panel';
        const bar = document.createElement('div'); bar.className = 'sg-comfy-bar';
        const title = document.createElement('strong'); title.textContent = 'SmartGallery'; bar.append(title);
        const button = (text, action) => { const b = document.createElement('button'); b.textContent = text; b.onclick = action; bar.append(b); return b; };
        const expand = button('Expand', () => {
          if (container.classList.contains('sg-expanded')) collapse();
          else { container.classList.add('sg-expanded'); expand.textContent = 'Collapse'; }
        }); expand.dataset.expand = '';
        button('Outputs', () => { frame.src = galleryUrl() + '/galleryout/'; });
        button('Library', () => { frame.src = galleryUrl() + '/galleryout/view/_root_?library='; });
        button('Reload', () => { frame.src = frame.src; });
        const link = document.createElement('a'); link.textContent = 'New tab ↗'; link.target = '_blank'; link.rel = 'noopener';
        const help = document.createElement('div'); help.className = 'sg-comfy-help'; help.textContent = 'Use Expand for the full gallery. If unavailable, run Start-SmartGallery.ps1.';
        container.append(bar, help);
        try {
          link.href = galleryUrl() + '/galleryout/'; bar.append(link);
          frame = document.createElement('iframe'); frame.title = 'SmartGallery media library'; frame.src = link.href;
          frame.referrerPolicy = 'origin'; container.append(frame);
        } catch (error) {
          const message = document.createElement('p'); message.className = 'sg-comfy-error'; message.textContent = error.message; container.append(message);
        }
        element.append(container);
      }
    });
  }
});
