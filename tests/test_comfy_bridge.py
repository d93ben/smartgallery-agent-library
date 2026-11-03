import importlib.util
import json
from pathlib import Path
from http.server import BaseHTTPRequestHandler, HTTPServer
import threading

import pytest


spec = importlib.util.spec_from_file_location('smartgallery_bridge', Path(__file__).parents[1] / 'integrations/comfyui_smartgallery/bridge.py')
bridge = importlib.util.module_from_spec(spec)
spec.loader.exec_module(bridge)


def test_bridge_local_request_boundary():
    assert bridge.local_request('127.0.0.1', '127.0.0.1:8188', 'http://127.0.0.1:8188', '1')
    assert bridge.local_request('::1', '[::1]:8188', None, '1')
    assert not bridge.local_request('192.168.1.2', '127.0.0.1:8188', None, '1')
    assert not bridge.local_request('127.0.0.1', 'attacker.test:8188', None, '1')
    assert not bridge.local_request('127.0.0.1', '127.0.0.1:8188', 'https://attacker.test', '1')
    assert not bridge.local_request('127.0.0.1', '127.0.0.1:8188', None, None)


def test_bridge_forwards_original_path_and_preserves_gallery_result(tmp_path):
    source = tmp_path / 'clip with spaces.mp4'
    source.write_bytes(b'original video bytes')
    received = []

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args): pass
        def do_POST(self):
            received.append((self.path, self.headers['X-SG-Library'], json.loads(self.rfile.read(int(self.headers['Content-Length'])))))
            self.send_response(200); self.end_headers()
            self.wfile.write(json.dumps({'created': False, 'record': {'id': 'keeper', 'title': 'Existing name', 'private': 'not returned'}}).encode())

    server = HTTPServer(('127.0.0.1', 0), Handler)
    worker = threading.Thread(target=server.serve_forever, daemon=True); worker.start()
    try:
        result = bridge.archive_path(source, [tmp_path], server.server_port)
        assert result == {'created': False, 'id': 'keeper', 'title': 'Existing name'}
        assert received == [('/galleryout/library/api/assets', '1', {'source_path': str(source.resolve()), 'actor': 'user'})]
        assert source.read_bytes() == b'original video bytes'
        with pytest.raises(ValueError): bridge.archive_path(source, [tmp_path / 'other'], server.server_port)
        text_file = tmp_path / 'notes.txt'; text_file.write_text('private note')
        with pytest.raises(ValueError): bridge.archive_path(text_file, [tmp_path], server.server_port)
    finally:
        server.shutdown(); server.server_close(); worker.join()
