"""Read, search and remove local Jarvis conversation history without opening the UI."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from core.memory.history import ConversationHistoryStore  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    cli=argparse.ArgumentParser(description='Jarvis 0.1.6.1 local conversation history')
    cli.add_argument('--db', type=Path, default=ROOT/'.runtime'/'memory'/'chat_history.sqlite3', help='Local SQLite history path')
    cli.add_argument('--owner', default='local-development-user', help='History owner ID')
    subs=cli.add_subparsers(dest='command',required=True)
    sessions=subs.add_parser('list',help='List recent conversation sessions')
    sessions.add_argument('--limit',type=int,default=30)
    show=subs.add_parser('show',help='Show a conversation')
    show.add_argument('session_id')
    show.add_argument('--limit',type=int,default=500)
    search=subs.add_parser('search',help='Search stored speech and replies')
    search.add_argument('query')
    search.add_argument('--limit',type=int,default=50)
    delete=subs.add_parser('delete-session',help='Permanently delete a session and its entries')
    delete.add_argument('session_id')
    delete.add_argument('--yes',action='store_true',help='Confirm permanent deletion')
    args=cli.parse_args(argv)
    if not args.db.is_file():
        print('No history database at:',args.db)
        return 1
    store=ConversationHistoryStore(args.db,owner_id=args.owner)
    if args.command=='list': result=store.sessions(args.limit)
    elif args.command=='show': result=store.entries(args.session_id,args.limit)
    elif args.command=='search': result=store.search(args.query,args.limit)
    else:
        if not args.yes:
            print('Refusing permanent deletion without --yes')
            return 2
        result={'deleted':store.delete_session(args.session_id)}
    print(json.dumps(result,indent=2,ensure_ascii=False))
    return 0


if __name__=='__main__':
    raise SystemExit(main())
