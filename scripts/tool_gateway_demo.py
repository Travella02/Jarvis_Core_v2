"""0.1.5.1 manual Core browser opener demonstration. Run only on a trusted desktop.

Default: exercise authorization and print what WOULD happen without opening a browser.
Explicit --open-youtube: call the actual system default browser, once.
"""
from __future__ import annotations
import argparse, asyncio
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from core.common.ids import CorrelationContext
from core.tools import ToolRequest
from core.tools.gateway import CoreToolGateway, ConfirmedUserAction

async def demo(live: bool) -> int:
    trace = CorrelationContext.create()
    request = ToolRequest(trace, "desktop_browser", "open_approved_site",
                          {"site":"youtube"}, idempotency_key=trace.request_id)
    if not live:
        gateway = CoreToolGateway(launch_browser=lambda url: True)
        print("SIMULATED: no browser will be opened.")
    else:
        gateway = CoreToolGateway()
        print("LIVE: requesting one YouTube tab in your system default browser.")
    result = await gateway.execute(request, evidence=ConfirmedUserAction(
        trace.turn_id, "Jarvis, open YouTube", confirmed=True, local_desktop=True))
    print(f"status={result.status.value} code={result.error_code or 'none'}")
    if live:
        print(result.output.get('user_message') or result.error_message or 'No change.')
    else:
        print('SIMULATED: Core would request the approved YouTube URL; nothing was opened.')
    return 0 if result.status.value == "succeeded" else 1

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('--open-youtube', action='store_true', help='Perform the real visible desktop action')
    args = parser.parse_args()
    raise SystemExit(asyncio.run(demo(args.open_youtube)))
