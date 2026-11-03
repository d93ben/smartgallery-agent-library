"""SmartGallery sidebar and local asset-menu bridge; no extra dependencies."""
import asyncio
import json
from pathlib import Path
from urllib.error import HTTPError, URLError
from uuid import UUID

from aiohttp import web
import folder_paths
from app.assets.services import resolve_asset_for_download
from server import PromptServer

from .bridge import archive_path, local_request


def keep_asset(asset_id):
    config = json.loads(Path(__file__).with_name('gallery.local.json').read_text(encoding='utf-8-sig'))
    settings = json.loads((Path(config['gallery_path']) / 'local.json').read_text(encoding='utf-8-sig'))
    # The asset content resolver returns the original, including for video cards
    # whose preview is a separate thumbnail. Never archive a preview URL.
    source = resolve_asset_for_download(reference_id=str(UUID(asset_id)), record_access=False).abs_path
    return archive_path(source, [folder_paths.get_input_directory(), folder_paths.get_output_directory()],
                        settings.get('port', 8189))


@PromptServer.instance.routes.post('/smartgallery/library/keep')
async def keep(request):
    if not local_request(request.remote, request.host, request.headers.get('Origin'), request.headers.get('X-SG-Library')):
        return web.json_response({'error': 'Use the local ComfyUI Media Library menu.'}, status=403)
    try:
        data = await request.json()
        result = await asyncio.to_thread(keep_asset, data['asset_id'])
        return web.json_response(result)
    except HTTPError:
        return web.json_response({'error': 'SmartGallery could not save this asset. Check its local server log.'}, status=502)
    except (URLError, TimeoutError):
        return web.json_response({'error': 'SmartGallery is unavailable. Run Start-SmartGallery.ps1 and try again.'}, status=503)
    except FileNotFoundError:
        return web.json_response({'error': 'The original file or gallery configuration is missing.'}, status=404)
    except (ValueError, KeyError, TypeError, AttributeError):
        return web.json_response({'error': 'Select a single image, video, or audio file in Media Assets.'}, status=400)


NODE_CLASS_MAPPINGS = {}
NODE_DISPLAY_NAME_MAPPINGS = {}
WEB_DIRECTORY = './web'
__all__ = ['NODE_CLASS_MAPPINGS', 'NODE_DISPLAY_NAME_MAPPINGS', 'WEB_DIRECTORY']
