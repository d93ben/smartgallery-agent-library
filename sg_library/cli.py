"""CLI fallback for agents without MCP. JSON in, JSON out."""
import argparse
import json
from pathlib import Path
import sys
from .client import Client


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--url', default=None)
    parser.add_argument('action', choices=['status', 'outputs', 'search', 'get', 'save', 'update', 'workflow', 'verify', 'restore'])
    parser.add_argument('value', nargs='?', default='')
    parser.add_argument('--json-file', help='UTF-8 JSON request body for save/update/restore')
    args = parser.parse_args()
    client = Client(args.url)
    data = json.loads(Path(args.json_file).read_text(encoding='utf-8-sig')) if args.json_file else {}
    paths = {'status': 'health', 'outputs': 'outputs', 'search': 'assets', 'get': 'assets/' + args.value,
             'workflow': 'assets/' + args.value + '/workflow', 'verify': 'assets/' + args.value + '/verify'}
    try:
        if args.action in ('search', 'outputs'):
            result = client.call(paths[args.action], q=args.value)
        elif args.action == 'save':
            result = client.call('assets', 'POST', {'source_path': args.value, **data})
        elif args.action in ('update', 'restore'):
            suffix = '/restore' if args.action == 'restore' else ''
            result = client.call('assets/' + args.value + suffix, 'POST' if suffix else 'PATCH', data)
        else:
            result = client.call(paths[args.action])
        print(json.dumps(result, ensure_ascii=False, indent=2))
    except RuntimeError as exc:
        print(json.dumps({'error': str(exc)}), file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
