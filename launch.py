"""Load private machine paths without editing upstream configuration."""
import json
import os
from pathlib import Path
import runpy


def configure(path=None):
    root = Path(__file__).resolve().parent
    config = json.loads(Path(path or root / 'local.json').read_text(encoding='utf-8-sig'))
    comfy = Path(config['comfy_path']).resolve(strict=True)
    library = Path(config['library_path']).resolve()
    for source in (comfy / 'output', comfy / 'input'):
        source = source.resolve()
        if library.is_relative_to(source) or source.is_relative_to(library):
            raise ValueError('Keep library_path separate from ComfyUI input and output folders.')
    settings = {
        'BASE_OUTPUT_PATH': str(comfy / 'output'), 'BASE_INPUT_PATH': str(comfy / 'input'),
        'BASE_MODELS_PATH': str(comfy / 'models'), 'BASE_SMARTGALLERY_PATH': config['data_path'],
        'SG_LIBRARY_PATH': config['library_path'], 'SG_HOST': '127.0.0.1',
        'SERVER_PORT': str(config.get('port', 8189)), 'SG_CHECK_UPDATES': 'false',
        'ENABLE_AI_SEARCH': 'false', 'PYTHONUTF8': '1',
    }
    os.environ.update(settings)
    for name in ('data_path', 'library_path'):
        Path(config[name]).mkdir(parents=True, exist_ok=True)
    if config.get('ffmpeg_directory'):
        os.environ['PATH'] = config['ffmpeg_directory'] + os.pathsep + os.environ['PATH']
    return root


if __name__ == '__main__':
    root = configure()
    os.chdir(root)
    runpy.run_path(str(root / 'smartgallery.py'), run_name='__main__')
