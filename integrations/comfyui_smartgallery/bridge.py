"""Local-only adapter from a ComfyUI asset to the existing library writer."""
import ipaddress
import json
from pathlib import Path
from urllib.parse import urlsplit
from urllib.request import Request, urlopen


MEDIA = {'.png', '.jpg', '.jpeg', '.webp', '.gif', '.mp4', '.webm', '.mkv', '.mov', '.avi', '.wav', '.mp3', '.flac', '.ogg'}


def local_request(remote, host, origin, client_header):
    try:
        return (ipaddress.ip_address(remote).is_loopback
                and urlsplit('http://' + host).hostname in ('localhost', '127.0.0.1', '::1')
                and (not origin or urlsplit(origin).netloc == host)
                and client_header == '1')
    except ValueError:
        return False


def archive_path(source, roots, port):
    source = Path(source).resolve(strict=True)
    if not any(source.is_relative_to(Path(root).resolve()) for root in roots):
        raise ValueError('Only ComfyUI input and output media can be added.')
    if not source.is_file() or source.suffix.lower() not in MEDIA:
        raise ValueError('Choose an image, video, or audio asset.')
    port = int(port)
    if not 1 <= port <= 65535:
        raise ValueError('Invalid local gallery port.')
    payload = json.dumps({'source_path': str(source), 'actor': 'user'}).encode('utf-8')
    request = Request(f'http://127.0.0.1:{port}/galleryout/library/api/assets', data=payload,
                      headers={'Content-Type': 'application/json', 'X-SG-Library': '1'})
    with urlopen(request, timeout=120) as response:
        result = json.load(response)
    record = result['record']
    return {'created': result['created'], 'id': record['id'], 'title': record['title']}
