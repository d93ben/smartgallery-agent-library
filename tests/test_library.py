import json
from pathlib import Path
import shutil
import subprocess

from flask import Flask
from PIL import Image, PngImagePlugin
import pytest

from sg_library.store import Conflict, Library, sha256
from sg_library.web import register


WORKFLOW = {'last_node_id': 2, 'last_link_id': 0, 'nodes': [
    {'id': 1, 'type': 'LoadImage', 'widgets_values': ['reference.png', 'image']},
    {'id': 2, 'type': 'Note', 'mode': 4, 'widgets_values': ['Muted nodes and notes must survive']}],
    'links': [], 'groups': [{'title': 'Original group'}], 'config': {}, 'extra': {}, 'version': 0.4}
PROMPT = {'1': {'class_type': 'LoadImage', 'inputs': {'image': 'reference.png'}}}


def extractor(path, target_type='ui'):
    try:
        with Image.open(path) as image:
            return image.info.get('workflow' if target_type == 'ui' else 'prompt')
    except Exception:
        if Path(path).suffix == '.json':
            return Path(path).read_text()
        return None


@pytest.fixture
def setup(tmp_path):
    output = tmp_path / 'output'; output.mkdir()
    inputs = tmp_path / 'input'; inputs.mkdir()
    Image.new('RGB', (24, 24), '#bb99ff').save(inputs / 'reference.png')
    meta = PngImagePlugin.PngInfo()
    meta.add_text('workflow', json.dumps(WORKFLOW)); meta.add_text('prompt', json.dumps(PROMPT))
    source = output / 'result.png'
    Image.new('RGB', (32, 32), '#162839').save(source, pnginfo=meta)
    return Library(tmp_path / 'library', [output, inputs], extractor), source, inputs


def test_original_workflow_and_references_survive_source_cleanup(setup):
    lib, source, inputs = setup
    expected = source.read_bytes()
    result = lib.archive(source); record = result['record']; key = record['id']
    assert result['created']
    assert lib.asset_file(key, record['original']['file']).read_bytes() == expected
    source.unlink(); (inputs / 'reference.png').unlink()
    assert lib.verify(key)['ok']
    assert lib.workflow(key) == WORKFLOW
    assert lib.workflow(key, 'api') == PROMPT
    prepared = lib.prepared_workflow(key, inputs)
    assert prepared['workflow']['nodes'][0]['widgets_values'][0].startswith('SmartGallery/')
    assert (inputs / prepared['workflow']['nodes'][0]['widgets_values'][0]).exists()
    assert lib.workflow(key) == WORKFLOW


def test_dedup_revision_conflict_history_and_restore(setup):
    lib, source, _ = setup
    record = lib.archive(source)['record']; key = record['id']
    assert lib.archive(source)['created'] is False
    facts = [{'key': 'Model', 'value': 'Example model', 'source_type': 'author', 'source_url': 'https://example.org/model'}]
    changed = lib.update(key, {'notes': 'First review', 'facts': facts, 'rating': 4}, 1, 'test-agent', 'Added sourced context')
    assert changed['revision'] == 2
    with pytest.raises(Conflict): lib.update(key, {'notes': 'Stale'}, 1, 'test-agent', 'Stale update')
    restored = lib.restore(key, 1, 2, 'user')
    assert restored['revision'] == 3 and restored['notes'] == ''
    assert restored['history'][1]['fields']['facts'] == facts
    assert restored['original'] == record['original']


def test_paths_immutable_evidence_and_invalid_edits(setup, tmp_path):
    lib, source, _ = setup
    outside = tmp_path / 'outside.png'; shutil.copy2(source, outside)
    with pytest.raises(ValueError): lib.archive(outside)
    with pytest.raises(ValueError): lib.folder('../output')
    key = lib.archive(source)['record']['id']
    with pytest.raises(ValueError): lib.asset_file(key, '../../outside.png')
    for patch in ({'original': {}}, {'rating': True}, {'rating': 6}, {'facts': [{'key': 'x', 'value': 'y', 'source_type': 'certain'}]}):
        with pytest.raises(ValueError): lib.update(key, patch, 1, 'test', 'Invalid')
    assert lib.read(key)['revision'] == 1


def test_format_fallback_never_mislabels_graph(setup):
    lib, source, _ = setup
    lib.extractor = lambda *args, **kwargs: json.dumps(PROMPT)
    record = lib.archive(source)['record']
    assert not record['original']['has_workflow']
    assert record['original']['has_prompt']
    with pytest.raises(FileNotFoundError): lib.workflow(record['id'])


def test_companion_workflow_and_missing_metadata(setup):
    lib, source, _ = setup
    Image.new('RGB', (32, 32), 'white').save(source)
    assert not lib.archive(source)['record']['original']['has_workflow']
    other = source.with_name('other.png'); Image.new('RGB', (32, 32), 'blue').save(other)
    other.with_suffix('.json').write_text(json.dumps(WORKFLOW))
    record = lib.archive(other)['record']
    assert record['original']['workflow_origins']['ui'] == 'companion:other.json'


def test_failed_copy_publishes_nothing(setup, monkeypatch):
    lib, source, _ = setup
    def fail(*args): raise OSError('Simulated disk failure')
    monkeypatch.setattr(lib, 'copy_verified', fail)
    with pytest.raises(OSError): lib.archive(source)
    assert list(lib.root.iterdir()) == []


def test_detects_corruption_and_does_not_overwrite_restored_edits(setup):
    lib, source, inputs = setup
    record = lib.archive(source)['record']; key = record['id']
    prepared = lib.prepared_workflow(key, inputs)
    (inputs / prepared['workflow']['nodes'][0]['widgets_values'][0]).write_bytes(b'user edited')
    with pytest.raises(Conflict): lib.prepared_workflow(key, inputs)
    (lib.folder(key) / 'workflow.json').write_text('{}')
    assert not lib.verify(key)['ok']


def test_api_mutation_and_local_access_boundaries(setup):
    lib, source, inputs = setup
    app = Flask(__name__)
    register(app, root=lib.root, sources=lib.source_roots, extractor=extractor,
             resolve_output=lambda _: {'path': str(source)}, accessible=lambda _: True,
             management=lambda f: f, connection=lambda: None, input_root=inputs)
    client = app.test_client(); prefix = '/galleryout/library/api'
    payload = {'source_path': str(source)}
    assert client.post(prefix + '/assets', json=payload).status_code == 403
    headers = {'X-SG-Library': '1'}
    assert client.post(prefix + '/assets', json=payload, headers={**headers, 'Origin': 'https://elsewhere.test'}).status_code == 403
    assert client.get(prefix + '/health', environ_overrides={'REMOTE_ADDR': '192.168.1.2'}).status_code == 403
    assert client.get(prefix + '/health', headers={'Host': 'rebind.example'}).status_code == 403
    response = client.post(prefix + '/assets', json=payload, headers=headers)
    assert response.status_code == 200
    record = response.json['record']
    update = {'fields': {'notes': 'HTTP test'}, 'actor': 'test', 'reason': 'Test', 'expected_revision': 1}
    assert client.patch(prefix + '/assets/' + record['id'], json=update, headers=headers).status_code == 200
    assert client.patch(prefix + '/assets/' + record['id'], json=update, headers=headers).status_code == 409
    assert client.get(prefix + '/assets/' + record['id'] + '/media').data == source.read_bytes()


def test_real_upstream_image_and_video_extraction(tmp_path, monkeypatch):
    ffmpeg = shutil.which('ffmpeg')
    if not ffmpeg: pytest.skip('ffmpeg required for real video metadata check')
    for name in ('BASE_OUTPUT_PATH', 'BASE_INPUT_PATH', 'BASE_SMARTGALLERY_PATH', 'SG_LIBRARY_PATH'):
        monkeypatch.setenv(name, str(tmp_path / name))
    import smartgallery
    workflow = {'nodes': [], 'links': [], 'groups': [], 'version': 0.4}
    prompt = {'1': {'class_type': 'EmptyImage', 'inputs': {'width': 64, 'height': 64}}}
    source = tmp_path / 'video.mp4'
    subprocess.run([ffmpeg, '-v', 'error', '-f', 'lavfi', '-i', 'color=c=navy:s=64x64:d=0.2', '-c:v', 'libx264', '-metadata', 'comment=' + json.dumps(workflow), '-metadata', 'description=' + json.dumps(prompt), str(source)], check=True, capture_output=True)
    lib = Library(tmp_path / 'keepers', [tmp_path], smartgallery.extract_workflow)
    record = lib.archive(source)['record']
    source.unlink()
    assert lib.verify(record['id'])['ok']
    assert lib.workflow(record['id']) == workflow
    assert lib.workflow(record['id'], 'api') == prompt
