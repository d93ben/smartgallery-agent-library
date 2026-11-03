"""Start the separately installed local gallery when ComfyUI starts."""
import json
import os
from pathlib import Path
import subprocess
from urllib.request import urlopen


def start():
    config_path = Path(__file__).with_name('gallery.local.json')
    if not config_path.exists():
        return
    config = json.loads(config_path.read_text(encoding='utf-8-sig'))
    root = Path(config['gallery_path']).resolve(strict=True)
    settings = json.loads((root / 'local.json').read_text(encoding='utf-8-sig'))
    port = int(settings.get('port', 8189))
    try:
        with urlopen(f'http://127.0.0.1:{port}/galleryout/library/api/health', timeout=2) as response:
            if json.load(response).get('service') == 'smartgallery-library':
                return
    except OSError:
        pass
    data = Path(settings['data_path']); data.mkdir(parents=True, exist_ok=True)
    python = root / ('.venv/Scripts/python.exe' if os.name == 'nt' else '.venv/bin/python')
    with (data / 'server.log').open('a', encoding='utf-8') as out, (data / 'server-error.log').open('a', encoding='utf-8') as err:
        subprocess.Popen([str(python), '-u', str(root / 'launch.py')], cwd=root, stdout=out, stderr=err,
                         env={**os.environ, 'PYTHONUTF8': '1'},
                         creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0,
                         start_new_session=os.name != 'nt')
    print('[SmartGallery] Starting the local gallery on port', port)


try:
    start()
except Exception as exc:
    print('[SmartGallery] Could not start the gallery:', exc)
