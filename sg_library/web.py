"""Narrow HTTP adapter; the gallery and agents share one writer."""
from functools import wraps
from pathlib import Path
from urllib.parse import urlsplit

from flask import Blueprint, jsonify, request, send_file
from werkzeug.exceptions import HTTPException

from .store import Conflict, Library


def register(app, *, root, sources, extractor, resolve_output, accessible, management, connection, input_root, clusterer=None):
    library = Library(root, sources, extractor, clusterer)
    api = Blueprint('keeper_library', __name__, url_prefix='/galleryout/library/api')

    @api.before_request
    @management
    def protect():
        # This private personal-library API is intentionally loopback-only, even
        # if an upstream gallery administrator enables LAN access elsewhere.
        if request.remote_addr not in ('127.0.0.1', '::1'):
            return jsonify(error='The personal library is available on this computer only.'), 403
        if urlsplit('http://' + request.host).hostname not in ('localhost', '127.0.0.1', '::1'):
            return jsonify(error='Invalid local host.'), 403
        origin = request.headers.get('Origin')
        if origin and urlsplit(origin).netloc != request.host:
            return jsonify(error='Cross-origin library access is disabled.'), 403
        if request.method not in ('GET', 'HEAD', 'OPTIONS') and request.headers.get('X-SG-Library') != '1':
            return jsonify(error='Library client header required.'), 403

    def route(rule, **options):
        def decorate(fn):
            @wraps(fn)
            def handle(*args, **kwargs):
                try:
                    return fn(*args, **kwargs)
                except Conflict as exc:
                    return jsonify(error=str(exc)), 409
                except FileNotFoundError:
                    return jsonify(error='File or workflow not found.'), 404
                except (ValueError, TypeError, KeyError) as exc:
                    return jsonify(error=str(exc)), 400
                except HTTPException:
                    raise
                except OSError as exc:
                    app.logger.exception('Library file operation failed')
                    return jsonify(error=f'File operation failed: {exc.strerror}'), 500
            api.route(rule, **options)(handle)
            return handle
        return decorate

    @route('/health')
    def health():
        return jsonify(service='smartgallery-library', version=1, library_root=str(library.root),
                       source_roots=[str(p) for p in library.source_roots], count=library.list(limit=1)['total'])

    @route('/assets')
    def search():
        return jsonify(library.list(request.args.get('q', ''), request.args.get('limit', 100)))

    @route('/outputs')
    def outputs():
        query = request.args.get('q', '')
        limit = max(1, min(int(request.args.get('limit', 50)), 200))
        with connection() as conn:
            rows = conn.execute('SELECT id,name,path,type,size,has_workflow FROM files WHERE name LIKE ? ORDER BY mtime DESC LIMIT ?', ('%' + query + '%', limit)).fetchall()
        return jsonify(items=[dict(row) for row in rows if accessible(row['id'])])

    @route('/assets', methods=['POST'])
    def archive():
        data = request.get_json()
        if data.get('file_id'):
            if not accessible(data['file_id']):
                return jsonify(error='This output is not accessible.'), 403
            source = resolve_output(data['file_id'])['path']
        else:
            source = data['source_path']
        return jsonify(library.archive(source, data.get('title', ''), data.get('collection', ''), data.get('actor', 'user')))

    @route('/assets/<asset_id>')
    def detail(asset_id):
        return jsonify(library.read(asset_id))

    @route('/assets/<asset_id>', methods=['PATCH'])
    def update(asset_id):
        data = request.get_json()
        return jsonify(library.update(asset_id, data['fields'], data['expected_revision'], data['actor'], data['reason']))

    @route('/assets/<asset_id>/restore', methods=['POST'])
    def restore(asset_id):
        data = request.get_json()
        return jsonify(library.restore(asset_id, data['revision'], data['expected_revision'], data['actor']))

    @route('/assets/<asset_id>/workflow')
    def workflow(asset_id):
        return jsonify(library.workflow(asset_id, request.args.get('kind', 'ui')))

    @route('/assets/<asset_id>/prepare', methods=['POST'])
    def prepare(asset_id):
        return jsonify(library.prepared_workflow(asset_id, input_root))

    @route('/assets/<asset_id>/verify')
    def verify(asset_id):
        return jsonify(library.verify(asset_id))

    @route('/assets/<asset_id>/media')
    def media(asset_id):
        record = library.read(asset_id)
        return send_file(library.asset_file(asset_id, record['original']['file']), conditional=True)

    app.register_blueprint(api)
    app.extensions['keeper_library'] = library
    return library
