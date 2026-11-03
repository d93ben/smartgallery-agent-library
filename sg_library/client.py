import json
import os
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urlsplit
from urllib.request import Request, urlopen


class Client:
    def __init__(self, url=None):
        self.url = (url or os.environ.get('SMARTGALLERY_URL', 'http://127.0.0.1:8189')).rstrip('/')
        parsed = urlsplit(self.url)
        if parsed.scheme != 'http' or parsed.hostname not in ('127.0.0.1', 'localhost', '::1'):
            raise ValueError('Use the local SmartGallery HTTP address.')

    def call(self, path, method='GET', data=None, **query):
        url = self.url + '/galleryout/library/api/' + path
        if query:
            url += '?' + urlencode(query)
        body = json.dumps(data).encode() if data is not None else None
        req = Request(url, data=body, method=method, headers={'Content-Type': 'application/json', 'X-SG-Library': '1'})
        try:
            with urlopen(req, timeout=180) as response:
                return json.load(response)
        except HTTPError as exc:
            try:
                message = json.load(exc)
            except (ValueError, UnicodeError):
                message = {'error': exc.reason}
            raise RuntimeError(f'{exc.code}: {message.get("error", message.get("message", str(message)))}') from exc
        except URLError as exc:
            raise RuntimeError('SmartGallery is not reachable. Start the gallery and try again.') from exc
