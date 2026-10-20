"""Read-only Windows app inventory diagnostics; never launches anything.

Usage: python .\\scripts\\app_inventory_probe.py Discord Spotify
Shows only names and source types, not full paths or executable arguments.
"""
from __future__ import annotations

import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.tools.app_discovery import InstalledAppInventory, normalize


def main() -> int:
    if os.name != 'nt':
        print('This diagnostic reads Windows application registrations. Run it on Windows.')
        return 2
    names = sys.argv[1:] or ['Discord', 'Spotify']
    inventory = InstalledAppInventory(auto_start=False)
    inventory._refresh()  # one bounded synchronous OS registration scan
    items = inventory.candidates()
    print(f'Discovered launch routes: {len(items)} (system + Start Menu + App Paths + Start apps)')
    for name in names[:12]:
        match, status = inventory.resolve(name)
        print(f'Query {name!r}: {status}' + (f' -> {match.name} ({match.source})' if match else ''))
        query = normalize(name)
        nearby = [item for item in items if query in normalize(item.name) or any(query in alias for alias in item.names)]
        for item in nearby[:12]:
            print(f'  route={item.source}, kind={item.kind}, name={item.name!r}')
        if len(nearby) > 12:
            print(f'  ... {len(nearby)-12} more related routes')
    print('Read-only check complete; no applications were launched.')
    return 0

if __name__ == '__main__':
    raise SystemExit(main())
