import asyncio
import json
import os
from pathlib import Path
import sys
import threading

from flask import Flask
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from PIL import Image, PngImagePlugin
from werkzeug.serving import make_server

from sg_library.web import register


def test_real_mcp_protocol_archives_and_edits(tmp_path):
    source = tmp_path / 'protocol.png'
    graph = {'nodes': [], 'links': [], 'version': 0.4}
    metadata = PngImagePlugin.PngInfo(); metadata.add_text('workflow', json.dumps(graph))
    Image.new('RGB', (16, 16), 'purple').save(source, pnginfo=metadata)
    def extract(path, target_type='ui'):
        with Image.open(path) as image:
            return image.info.get('workflow') if target_type == 'ui' else None
    app = Flask(__name__)
    register(app, root=tmp_path / 'keepers', sources=[tmp_path], extractor=extract,
             resolve_output=lambda _: {'path': str(source)}, accessible=lambda _: True,
             management=lambda f: f, connection=lambda: None, input_root=tmp_path)
    server = make_server('127.0.0.1', 0, app)
    thread = threading.Thread(target=server.serve_forever, daemon=True); thread.start()
    params = StdioServerParameters(command=sys.executable,
        args=[str(Path(__file__).resolve().parents[1] / 'agent_mcp.py')],
        env={**os.environ, 'SMARTGALLERY_URL': f'http://127.0.0.1:{server.server_port}'})

    async def exercise():
        async with stdio_client(params) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                names = {tool.name for tool in (await session.list_tools()).tools}
                assert {'save_keeper', 'update_metadata', 'restore_metadata', 'get_workflow', 'verify_archive'} <= names
                async def call(name, data):
                    result = await session.call_tool(name, data)
                    assert not result.isError, result.content
                    return result.structuredContent or json.loads(result.content[0].text)
                saved = await call('save_keeper', {'source_path': str(source), 'actor': 'protocol-test'})
                key = saved['record']['id']
                assert saved['record']['original']['has_workflow']
                changed = await call('update_metadata', {'asset_id': key, 'expected_revision': 1,
                    'fields': {'tags': ['tested'], 'facts': [{'key': 'Check', 'value': 'MCP protocol', 'source_type': 'verified'}]},
                    'actor': 'protocol-test', 'reason': 'End-to-end integration test'})
                assert changed['revision'] == 2
                source.unlink()
                assert (await call('verify_archive', {'asset_id': key}))['ok']
                assert (await call('get_workflow', {'asset_id': key})) == graph
                assert (await call('search_library', {'query': 'tested'}))['total'] == 1
                restored = await call('restore_metadata', {'asset_id': key, 'revision': 1, 'expected_revision': 2, 'actor': 'protocol-test'})
                assert restored['revision'] == 3 and restored['tags'] == []
    try:
        asyncio.run(exercise())
    finally:
        server.shutdown(); thread.join(timeout=5)
