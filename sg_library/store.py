import copy
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import threading
from datetime import datetime, timezone
from uuid import uuid4


MEDIA = {'.png', '.jpg', '.jpeg', '.webp', '.gif', '.mp4', '.webm', '.mkv', '.mov', '.avi', '.wav', '.mp3', '.flac', '.ogg'}
EDITABLE = {'title', 'notes', 'tags', 'collection', 'rating', 'facts'}


def now():
    return datetime.now(timezone.utc).isoformat()


def sha256(path):
    with open(path, 'rb') as f:
        return hashlib.file_digest(f, 'sha256').hexdigest()


def atomic_json(path, value):
    temp = path.with_name(path.name + '.' + uuid4().hex + '.tmp')
    try:
        with temp.open('w', encoding='utf-8', newline='\n') as f:
            json.dump(value, f, ensure_ascii=False, indent=2, allow_nan=False)
            f.write('\n')
            f.flush()
            os.fsync(f.fileno())
        os.replace(temp, path)
    finally:
        temp.unlink(missing_ok=True)


class Conflict(ValueError):
    pass


class Library:
    def __init__(self, root, source_roots, extractor, clusterer=None):
        self.root = Path(root).resolve()
        self.root.mkdir(parents=True, exist_ok=True)
        self.source_roots = [Path(p).resolve() for p in source_roots]
        self.extractor = extractor
        self.clusterer = clusterer
        self.lock = threading.RLock()

    def folder(self, asset_id):
        if not re.fullmatch(r'[0-9a-f]{32}', asset_id):
            raise ValueError('Invalid library ID.')
        folder = (self.root / asset_id).resolve()
        if not folder.is_relative_to(self.root):
            raise ValueError('Invalid library path.')
        return folder

    def read(self, asset_id):
        return json.loads((self.folder(asset_id) / 'record.json').read_text(encoding='utf-8'))

    def list(self, query='', limit=100):
        limit = max(1, min(int(limit), 500))
        rows = []
        for record_path in self.root.glob('*/record.json'):
            if not re.fullmatch(r'[0-9a-f]{32}', record_path.parent.name):
                continue
            record = self.read(record_path.parent.name)
            editorial = {k: record[k] for k in EDITABLE}
            haystack = json.dumps([editorial, record['original']['filename']], ensure_ascii=False).casefold()
            if all(word in haystack for word in query.casefold().split()):
                rows.append({**editorial, 'id': record['id'], 'revision': record['revision'],
                             'created_at': record['created_at'], 'updated_at': record['updated_at'],
                             'filename': record['original']['filename'], 'has_workflow': record['original']['has_workflow'],
                             'clustering': record.get('clustering', {})})
        rows.sort(key=lambda r: r['updated_at'], reverse=True)
        return {'total': len(rows), 'items': rows[:limit]}

    def source(self, path):
        path = Path(path).resolve(strict=True)
        if not path.is_file() or path.suffix.lower() not in MEDIA:
            raise ValueError('Choose a supported image, video, or audio file.')
        if not any(path.is_relative_to(root) for root in self.source_roots + [self.root]):
            raise ValueError('File is outside the configured media folders.')
        return path

    def reference_manifest(self, workflow, folder):
        references = []
        if not isinstance(workflow, dict):
            return references
        # Only capture input widgets of known media loader nodes, never prompt text.
        for node in workflow.get('nodes', []):
            node_type = str(node.get('type', ''))
            if not any(term in node_type.lower() for term in ('loadimage', 'loadvideo', 'loadaudio', 'load_video', 'load_audio', 'load_image')):
                continue
            widgets = node.get('widgets_values', [])
            values = widgets.values() if isinstance(widgets, dict) else widgets if isinstance(widgets, list) else []
            for value in values:
                if not isinstance(value, str) or len(value) > 1024:
                    continue
                filename = re.sub(r' \[(input|output|temp)\]$', '', value)
                if Path(filename).suffix.lower() not in MEDIA:
                    continue
                absolute = Path(filename).is_absolute()
                entry = {'node_id': node.get('id'), 'value': value, 'absolute_path': absolute, 'status': 'unresolved'}
                annotated = re.search(r' \[(input|output)\]$', value)
                roots = self.source_roots
                if annotated:
                    roots = sorted(roots, key=lambda root: root.name.lower() != annotated.group(1))
                candidates = [Path(filename)] if absolute else [root / filename for root in roots]
                for candidate in candidates:
                    try:
                        source = self.source(candidate)
                    except (ValueError, FileNotFoundError, OSError):
                        continue
                    dest_dir = folder / 'references'
                    dest_dir.mkdir(exist_ok=True)
                    dest = dest_dir / (str(len(references)) + '_' + source.name)
                    digest = self.copy_verified(source, dest)
                    entry.update(status='copied', file=dest.relative_to(folder).as_posix(), sha256=digest)
                    break
                references.append(entry)
        return references

    @staticmethod
    def copy_verified(source, dest):
        before = source.stat()
        shutil.copy2(source, dest)
        digest = sha256(dest)
        after = source.stat()
        if (before.st_size, before.st_mtime_ns) != (after.st_size, after.st_mtime_ns) or digest != sha256(source):
            dest.unlink(missing_ok=True)
            raise Conflict('Source changed while copying. Wait for the save to finish and try again.')
        return digest

    def extract(self, copied, source):
        found, origins = {}, {}
        candidates = [copied, source.with_suffix('.json'), source.with_suffix('.png'), source.with_name(source.stem + '.workflow.json')]
        for candidate in candidates:
            if not candidate.is_file():
                continue
            for requested in ('ui', 'api'):
                text = self.extractor(str(candidate), target_type=requested)
                if not text:
                    continue
                data = json.loads(text)
                # Upstream can return the other format as a fallback. Never label
                # an execution prompt as a complete editable UI graph (or vice versa).
                if isinstance(data, dict) and isinstance(data.get('nodes'), list):
                    kind = 'ui'
                elif isinstance(data, dict) and any(isinstance(v, dict) and 'class_type' in v for v in data.values()):
                    kind = 'api'
                else:
                    continue
                if kind not in found:
                    found[kind] = data
                    origins[kind] = 'embedded' if candidate == copied else 'companion:' + candidate.name
            if len(found) == 2:
                break
        return found.get('ui'), found.get('api'), origins

    def archive(self, source_path, title='', collection='', actor='user'):
        source = self.source(source_path)
        with self.lock:
            digest = sha256(source)
            for path in self.root.glob('*/record.json'):
                if not re.fullmatch(r'[0-9a-f]{32}', path.parent.name):
                    continue
                record = self.read(path.parent.name)
                if record['original']['sha256'] == digest:
                    media = self.folder(record['id']) / record['original']['file']
                    if not media.is_file() or sha256(media) != digest:
                        raise Conflict('An existing keeper is missing or damaged. Restore it from backup before saving again.')
                    return {'created': False, 'record': record}
            asset_id = uuid4().hex
            staging = self.root / ('.pending-' + asset_id)
            staging.mkdir()
            try:
                media_dir = staging / 'media'
                media_dir.mkdir()
                copied = media_dir / source.name
                digest = self.copy_verified(source, copied)
                workflow, prompt, origins = self.extract(copied, source)
                if sha256(source) != digest:
                    raise Conflict('Source changed while extracting metadata. Try again when saving is complete.')
                if workflow:
                    atomic_json(staging / 'workflow.json', workflow)
                if prompt:
                    atomic_json(staging / 'prompt.json', prompt)
                record = {'schema_version': 1, 'id': asset_id, 'revision': 1,
                          'created_at': now(), 'updated_at': now(), 'title': title or source.stem,
                          'collection': collection, 'notes': '', 'tags': [], 'rating': None, 'facts': [],
                          'original': {'file': 'media/' + source.name, 'filename': source.name,
                                       'source_path': str(source), 'sha256': digest, 'size': copied.stat().st_size,
                                       'has_workflow': bool(workflow), 'has_prompt': bool(prompt), 'workflow_origins': origins},
                          'references': self.reference_manifest(workflow, staging),
                          'workflow_files': {name: sha256(staging / name) for name in ('workflow.json', 'prompt.json') if (staging / name).exists()},
                          'history': []}
                if self.clusterer and (prompt or workflow):
                    workflow_hash, prompt_hash = self.clusterer(None, wf_json=json.dumps(prompt or workflow))
                    record['clustering'] = {'workflow': workflow_hash, 'prompt': prompt_hash}
                self.validate({k: record[k] for k in EDITABLE})
                record['history'].append(self.event(record, actor, 'Saved original media and embedded workflow'))
                atomic_json(staging / 'record.json', record)
                os.replace(staging, self.folder(asset_id))
                return {'created': True, 'record': record}
            except Exception:
                # This directory was created above and is never a user supplied path.
                shutil.rmtree(staging)
                raise

    def validate(self, patch):
        if not isinstance(patch, dict) or set(patch) - EDITABLE:
            raise ValueError('Only title, notes, tags, collection, rating, and facts can be edited.')
        for key in ('title', 'collection', 'notes'):
            if key in patch and (not isinstance(patch[key], str) or len(patch[key]) > (100000 if key == 'notes' else 500)):
                raise ValueError('Invalid ' + key + '.')
        if 'rating' in patch and patch['rating'] is not None and (type(patch['rating']) is not int or not 1 <= patch['rating'] <= 5):
            raise ValueError('Rating must be 1–5, or null to clear.')
        if 'tags' in patch and (not isinstance(patch['tags'], list) or len(patch['tags']) > 100 or any(not isinstance(x, str) or len(x) > 100 for x in patch['tags'])):
            raise ValueError('Tags must be a list of short strings.')
        if 'facts' in patch:
            if not isinstance(patch['facts'], list) or len(patch['facts']) > 500:
                raise ValueError('Facts must be a list (maximum 500).')
            for fact in patch['facts']:
                allowed = {'key', 'value', 'source_url', 'source_type', 'checked_at', 'notes'}
                if not isinstance(fact, dict) or set(fact) - allowed or not {'key', 'value', 'source_type'} <= set(fact):
                    raise ValueError('Each fact needs key, value, and source_type.')
                if any(not isinstance(v, str) or len(v) > 10000 for v in fact.values()):
                    raise ValueError('Fact fields must be text.')
                if fact['source_type'] not in ('user', 'author', 'verified', 'inferred'):
                    raise ValueError('source_type must be user, author, verified, or inferred.')
                if fact.get('source_url') and not re.match(r'^https?://[^\s]+$', fact['source_url']):
                    raise ValueError('Source links must start with http:// or https://.')

    @staticmethod
    def event(record, actor, reason):
        if not isinstance(actor, str) or not actor.strip() or len(actor) > 200:
            raise ValueError('An actor name is required.')
        if not isinstance(reason, str) or not reason.strip() or len(reason) > 1000:
            raise ValueError('A short reason is required.')
        return {'revision': record['revision'], 'at': record['updated_at'], 'actor': actor,
                'reason': reason, 'fields': {key: copy.deepcopy(record[key]) for key in EDITABLE}}

    def update(self, asset_id, patch, expected_revision, actor, reason):
        self.validate(patch)
        with self.lock:
            record = self.read(asset_id)
            if expected_revision != record['revision']:
                raise Conflict('This record changed. Reload it before saving.')
            record.update(copy.deepcopy(patch))
            record['revision'] += 1
            record['updated_at'] = now()
            record['history'].append(self.event(record, actor, reason))
            atomic_json(self.folder(asset_id) / 'record.json', record)
            return record

    def restore(self, asset_id, revision, expected_revision, actor):
        with self.lock:
            record = self.read(asset_id)
            target = next((h for h in record['history'] if h['revision'] == revision), None)
            if target is None:
                raise ValueError('Revision not found.')
            return self.update(asset_id, target['fields'], expected_revision, actor, f'Restored editorial revision {revision}')

    def workflow(self, asset_id, kind='ui'):
        if kind not in ('ui', 'api'):
            raise ValueError('Workflow kind must be ui or api.')
        filename = 'workflow.json' if kind == 'ui' else 'prompt.json'
        return json.loads((self.folder(asset_id) / filename).read_text(encoding='utf-8'))

    def asset_file(self, asset_id, relative):
        folder = self.folder(asset_id)
        path = (folder / relative).resolve()
        if not path.is_relative_to(folder):
            raise ValueError('Invalid asset path.')
        return path

    def prepared_workflow(self, asset_id, input_root):
        """Return a copy with archived media references restored under input/."""
        with self.lock:
            if not self.verify(asset_id)['ok']:
                raise Conflict('Archive verification failed. Restore damaged files from backup first.')
            workflow = self.workflow(asset_id)
            record = self.read(asset_id)
            input_root = Path(input_root).resolve(strict=True)
            destination = (input_root / 'SmartGallery' / asset_id).resolve()
            if not destination.is_relative_to(input_root):
                raise ValueError('Invalid reference destination.')
            replacements = {}
            for ref in record['references']:
                if ref['status'] != 'copied':
                    continue
                destination.mkdir(parents=True, exist_ok=True)
                target = destination / Path(ref['file']).name
                if target.exists() and sha256(target) != ref['sha256']:
                    raise Conflict('A restored reference was edited. Keep that edit before restoring again.')
                if not target.exists():
                    self.copy_verified(self.asset_file(asset_id, ref['file']), target)
                replacements[(str(ref['node_id']), ref['value'])] = str(target) if ref.get('absolute_path') else target.relative_to(input_root).as_posix()
            for node in workflow.get('nodes', []):
                widgets = node.get('widgets_values', [])
                if isinstance(widgets, list):
                    node['widgets_values'] = [replacements.get((str(node.get('id')), v), v) if isinstance(v, str) else v for v in widgets]
                elif isinstance(widgets, dict):
                    node['widgets_values'] = {k: replacements.get((str(node.get('id')), v), v) if isinstance(v, str) else v for k, v in widgets.items()}
            return {'workflow': workflow, 'unresolved_references': self.verify(asset_id)['unresolved_references']}

    def verify(self, asset_id):
        record = self.read(asset_id)
        folder = self.folder(asset_id)
        files = [{'file': record['original']['file'], 'sha256': record['original']['sha256']}]
        files += [r for r in record['references'] if r['status'] == 'copied']
        files += [{'file': name, 'sha256': digest} for name, digest in record.get('workflow_files', {}).items()]
        checks = [{'file': f['file'], 'ok': self.asset_file(asset_id, f['file']).is_file() and sha256(self.asset_file(asset_id, f['file'])) == f['sha256']} for f in files]
        return {'id': asset_id, 'ok': all(f['ok'] for f in checks), 'files': checks,
                'unresolved_references': [r for r in record['references'] if r['status'] != 'copied']}
