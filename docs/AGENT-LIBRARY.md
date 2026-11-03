# SmartGallery Library

An independent fork of [SmartGallery DAM](https://github.com/biagiomaf/smart-comfyui-gallery), based on v2.24.4 (`ff25539`). The original author and contributors retain their MIT attribution. See [LICENSE](../LICENSE).

## Windows installation

Use Python 3.10+ and FFmpeg/ffprobe on PATH. Install into a separate folder, outside ComfyUI output. From this checkout:

```powershell
.\Install.ps1 -ComfyPath 'C:\ComfyUI\ComfyUI' -DataPath 'C:\SmartGallery-Data' -LibraryPath 'C:\Media-Library'
.\Start-SmartGallery.ps1
```

The installer uses its own `.venv`, writes ignored machine settings to `local.json`, and copies a dependency-free sidebar extension into ComfyUI's `custom_nodes/comfyui_smartgallery`. It does not install packages into ComfyUI's Python environment. Existing `local.json` is preserved when rerunning the installer; edit it explicitly to change paths. The extension's ignored `gallery.local.json` points to this checkout.

Restart ComfyUI once, then refresh its browser page. Look for **SmartGallery**, with the stacked-picture icon on the left. **Expand** opens the full gallery inside ComfyUI; **Library** jumps to keepers. **New tab** opens the standalone gallery. The extension starts the separate gallery automatically on future ComfyUI launches. Closing ComfyUI does not stop an already running gallery.

Default local URLs:
- Gallery: `http://127.0.0.1:8189/galleryout/`
- Keepers: `http://127.0.0.1:8189/galleryout/view/_root_?library=`

For a different port, edit `local.json`, set the matching **SmartGallery local address** in ComfyUI settings, and set `SMARTGALLERY_URL` for agent clients. Restart the gallery after changing its settings. Other operating systems can use their normal virtual environment, `pip install -r requirements-agent.txt`, an adapted `local.example.json`, and `python launch.py`; the PowerShell installer is Windows-specific.

## Keep, annotate, reopen

1. Open an output in the gallery and choose **◇ Keep**. Batch selection also has **Keep in Library** in its More menu.
2. The gallery copies the original bytes into the separate library, extracts available workflows, and captures resolvable references from common top-level media loader nodes. Byte-identical files return the existing keeper.
3. In **Library**, edit title, collection, tags, rating, notes, or sourced facts. Save creates a revision with actor and reason. History can restore older metadata as a new revision.
4. **Verify files** checks hashes for the saved media, workflow JSON, and captured reference media.
5. **Open workflow in ComfyUI** restores captured reference files under `input/SmartGallery/<id>/`, adjusts paths in a temporary graph copy, and uses ComfyUI's normal loader. The archived original graph is unchanged. No generation is queued. In the standalone gallery, this button downloads that restored graph.

The original file keeps its embedded metadata because it is copied without re-encoding. The UI graph and API execution prompt are also saved as separate JSON when available. Files lacking metadata are clearly marked; the software cannot recover a graph that was never saved. Adjacent same-stem `.json`, `.png`, and `.workflow.json` companions are checked when necessary, and companion provenance is recorded.

Keeper grouping reuses upstream structural workflow and positive-prompt hashes. These are organization aids, not integrity hashes or proof of identical generation settings. Search and grouping operate over up to 100 displayed matches; narrow your search for larger libraries. Integrity checks use SHA-256.

Library ratings and notes belong to the portable keeper record. They are separate from upstream output-gallery multi-user ratings/comments. Models, custom nodes, arbitrary file-loader formats, and media references inside nested subgraphs are not automatically bundled. Unresolved known media references are reported. A saved workflow is not a guarantee it will generate successfully on another installation.

You can also right-click an individual asset in ComfyUI's **Media Assets** panel and choose **Add to Media Library**. A confirmation appears when its independent copy is saved; existing keepers are detected without duplicating them. This works with local input/output images, videos, and audio. The menu uses the asset's original file, never its preview thumbnail. Restart ComfyUI after installing or updating this integration.

The installed frontend currently has no public Media Assets context-menu hook, so the extension adds a rendered menu item using the card's `data-asset-id`. A small loopback-only ComfyUI route resolves the original asset and forwards it to the gallery's existing writer. It uses ComfyUI's bundled dependencies and requires its assets API. No ComfyUI core files or gallery CORS settings are changed.

## Agent integration

Add the stdio MCP server to Codex (replace the checkout path):

```powershell
codex mcp add smartgallery -- 'C:\SmartGallery\.venv\Scripts\python.exe' 'C:\SmartGallery\agent_mcp.py'
```

Copy `agent-skill/smartgallery-library` into your Codex skills directory. Start a new chat or reload the client so the tools and skill are discovered. Other local MCP clients can use the same command and arguments. A hosted ChatGPT/Grok web chat cannot directly access this computer's stdio server; use a client with local tool access. The CLI fallback works immediately from the checkout:

```powershell
.\.venv\Scripts\python.exe -m sg_library.cli status
.\.venv\Scripts\python.exe -m sg_library.cli outputs 'filename'
.\.venv\Scripts\python.exe -m sg_library.cli search 'project'
```

Available tools: `library_status`, `search_outputs`, `search_library`, `save_keeper`, `get_asset`, `update_metadata`, `get_workflow`, `verify_archive`, and `restore_metadata`.

Example requests:
- “Keep this video under Character Tests and record what we changed.”
- “Find the author's documentation for the LoRAs in this keeper; add source links and trigger words without changing its generation metadata.”
- “Show the keeper's original workflow and verify its files.”

Updates require the latest revision, actor, and reason. Facts label evidence as user, author, verified, or inferred, with optional source URL/date. Concurrent stale edits fail instead of silently replacing another agent's work. The skill explains how to reread and merge. There are no library deletion or generation tools.

## Storage, privacy, and recovery

Each keeper is a self-contained folder with `record.json`, `media/`, available `workflow.json` and `prompt.json`, and any captured `references/`. Stable random IDs survive file renaming and do not depend on ComfyUI history. Metadata/history live in readable JSON, independent of the upstream SQLite index. Back up the entire library folder; a copy on the same disk does not protect against disk failure.

The launcher binds to `127.0.0.1`, disables automatic upstream update checks, and leaves optional AI indexing off. Normal browsing, saving, grouping, and metadata edits need no account, payment, or internet after installation. Agent web research uses internet. A hosted agent can receive metadata that its tools read; this is not an offline AI service. Upstream semantic AI features are not installed by this fork's basic setup.

The library API additionally requires loopback access, validates local Host/Origin, and requires a custom header for mutations. It honors upstream management permissions. It is a personal local API, not a multi-user authenticated service; do not expose it or reverse-proxy it to the internet. In upstream forced-login mode, stdio/CLI clients need an authenticated integration not provided here.

Clearing ComfyUI jobs/history does not affect keepers. Clearing source output files does not affect verified saved copies. Never place the permanent library under output, create an output junction pointing into it, or include it in a cleanup script's targets. The application does not perform cleanup for you.

## Development checks

```powershell
.\.venv\Scripts\python.exe -m pip install pytest
.\.venv\Scripts\python.exe -m pytest tests -q
node --check templates/js/library.js
node --check integrations/comfyui_smartgallery/web/smartgallery.js
```

Tests cover byte preservation, complete graph retention, source cleanup, reference restoration, deduplication, metadata conflict/history/restore, path and HTTP boundaries, copy failure, corruption detection, real FFmpeg video metadata extraction, and a real stdio MCP session against the HTTP service. FFmpeg is required for the video test. No GPU generation is required.

Update the fork deliberately with Git; do not replace it with an upstream Docker image or run an upstream installer over the modified checkout. Runtime folders, logs, private config, and environments are excluded from Git. Keep the upstream remote for future merges and review conflicts in the few integration hooks.
