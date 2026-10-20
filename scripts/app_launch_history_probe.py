"""Read-only local app launch history summary (no browser URL or speech data)."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.tools.app_launch_history import default_history_path


def main() -> int:
    parser = argparse.ArgumentParser(description='Inspect Jarvis local installed-app launch history.')
    parser.add_argument('--paths', action='store_true', help='Also display local installed app route targets.')
    args = parser.parse_args()
    path = default_history_path()
    if not path.is_file() or path.is_symlink():
        print('No application launches recorded yet.')
        return 0
    try:
        if path.stat().st_size > 150_000:
            print('App history file is unexpectedly large; cannot inspect safely.')
            return 1
        data = json.loads(path.read_text(encoding='utf-8'))
    except (OSError, ValueError):
        print('App history unavailable or malformed.')
        return 1
    if not isinstance(data, dict) or data.get('version') != 1:
        print('Unsupported app history format.')
        return 1
    recent = data.get('recent', [])
    preferred = data.get('preferred', {})
    if not isinstance(recent, list) or not isinstance(preferred, dict):
        print('App history unavailable or malformed.')
        return 1
    print(f'Local app history: {len(recent)} recent handoffs; {len(preferred)} cached preferred routes.')
    for item in recent[-12:]:
        if not isinstance(item, dict):
            continue
        app = str(item.get('app', '?')).replace('\n', ' ')[:90]
        source = str(item.get('source', '?'))[:40]
        outcome = str(item.get('result', '?'))[:40]
        line = f'  {app}: {outcome} via {source}'
        if args.paths:
            line += '  ' + str(item.get('target', ''))[:250]
        print(line)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
