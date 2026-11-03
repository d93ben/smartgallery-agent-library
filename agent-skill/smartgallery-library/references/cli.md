# CLI fallback

Run from the SmartGallery checkout using its own environment. The default URL is `http://127.0.0.1:8189`; override with `--url` before the action or `SMARTGALLERY_URL`.

```powershell
.\.venv\Scripts\python.exe -m sg_library.cli status
.\.venv\Scripts\python.exe -m sg_library.cli outputs 'filename fragment'
.\.venv\Scripts\python.exe -m sg_library.cli search 'tag or title'
.\.venv\Scripts\python.exe -m sg_library.cli save 'C:\ComfyUI\output\image.png'
.\.venv\Scripts\python.exe -m sg_library.cli get ASSET_ID
.\.venv\Scripts\python.exe -m sg_library.cli workflow ASSET_ID
.\.venv\Scripts\python.exe -m sg_library.cli verify ASSET_ID
.\.venv\Scripts\python.exe -m sg_library.cli update ASSET_ID --json-file 'C:\Temp\asset-update.json'
```

Write update JSON with a structured file-writing tool, preserving actual newlines and avoiding shell interpolation of untrusted notes. Example request body:

```json
{
  "expected_revision": 1,
  "actor": "Codex",
  "reason": "Added a user-requested research note",
  "fields": {"notes": "Read the existing record before merging this field."}
}
```

`save --json-file` optionally accepts `title`, `collection`, and `actor`. `restore ASSET_ID --json-file` needs `revision`, `expected_revision`, and `actor`. A 409 means reread and merge. CLI errors are JSON on stderr with a nonzero exit status.

The local installation's checkout path can be found in the ComfyUI extension's `custom_nodes/comfyui_smartgallery/gallery.local.json`. In a configured Codex client, `codex mcp get smartgallery` also identifies its command. Do not print unrelated client configuration or secrets.
