# SmartGallery Library fork

Preserve the upstream MIT license and attribution. Keep upstream changes narrow;
library storage, HTTP, and agent behavior belong in `sg_library/`.

The gallery is the single metadata writer. Agents use its HTTP API through MCP
or CLI; do not write the gallery database or keeper records directly. Original
media and generation graphs are immutable. All editorial changes record actor,
reason, and revision, and reject stale revisions.

Never commit private machine configuration, media, metadata records, prompts,
gallery databases, logs, or the Python environment. `local.json` is ignored.
Library/data directories should be outside this checkout and outside ComfyUI
output; do not create junctions from output into the permanent library.

Run `python -m pytest tests -q` in the separate gallery environment after storage
or API changes. Video extraction tests require FFmpeg. Check frontend syntax with
`node --check`. Browser-test the Library controls and ComfyUI sidebar when UI
changes. Distinguish a graph opening from a successful generation; never queue a
generation merely to test the sidebar.

Keep `integrations/comfyui_smartgallery` dependency-free. Do not change ComfyUI
core, installed Python packages, models, workflows, or queue history to add this
gallery. A local installation uses its private `gallery.local.json` to start the
separate gallery process at ComfyUI startup.
