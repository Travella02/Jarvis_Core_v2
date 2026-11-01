"""Conservative foreground-disruption guard for physical input and app launches.

Not an anti-cheat detector or bypass. Full-screen/known-protected processes are
best-effort signals; users must not rely on this as anti-cheat certification.
"""
from __future__ import annotations
import os
import re
from typing import Any

# This list is NOT complete, and is not a trigger for special behavior in games.
# Include common launchers/protected executables only as defense-in-depth.
DEFAULT_PROTECTED = ('rocketleague.exe','valorant-win64-shipping.exe',
    'fortniteclient-win64-shipping.exe','cs2.exe','league of legends.exe',
    'overwatch.exe','r5apex.exe','cod.exe','eldenring.exe','robloxplayerbeta.exe')


def protected_processes(env: dict[str,str] | None = None) -> set[str]:
    e = os.environ if env is None else env
    extra = e.get('JARVIS_PROTECTED_PROCESSES','')
    return set(DEFAULT_PROTECTED) | {p.lower().strip() for p in extra.split(',')
        if re.fullmatch(r'[\w .-]+\.exe',p.strip(),re.I)}


def foreground_disruption_reason(driver: Any, window: Any, env: dict[str,str] | None = None) -> str | None:
    """Fail closed when a foreground activity looks protected/immersive."""
    if str(window.process).lower() in protected_processes(env):
        return 'protected_application_active'
    check = getattr(driver,'is_fullscreen',None)
    # If a driver does not have a fullscreen capability (inert mock), its
    # result is not authoritative; production Windows driver always provides it.
    if callable(check):
        try:
            if check(window):return 'immersive_foreground_active'
        except Exception:
            return 'foreground_check_unavailable'
    return None


def user_activity_reason(driver: Any, min_idle: float = 1.5) -> str | None:
    idle=getattr(driver,'idle_seconds',None)
    if callable(idle):
        try:
            value=idle()
            if value is None or value < 0:return 'user_activity_check_unavailable'
            if value < min_idle:return 'user_currently_active'
        except Exception:return 'user_activity_check_unavailable'
    return None


def protect_existing_desktop_action(env: dict[str,str] | None = None) -> str | None:
    """Check before legacy actions that may launch/activate windows.

    Never inject input or alter focus during inspection. Non-Windows is inert.
    """
    if os.name != 'nt':return None
    try:
        from core.tools.terra_navigation import WindowsForegroundDriver
        driver=WindowsForegroundDriver()
        window=driver.identity()
        return foreground_disruption_reason(driver,window,env)
    except Exception:
        # Do not risk an intrusive action if the Windows foreground cannot be read.
        return 'foreground_check_unavailable'
