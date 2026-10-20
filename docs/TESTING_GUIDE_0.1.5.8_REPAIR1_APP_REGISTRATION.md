# Repair 1 Windows testing

Precondition: Candidate 1 0.1.5.8 installed and no local modifications since applying it. Any STOP message means do not force installation.

Tests (PowerShell, one command per step):
- `python .\apply_0_1_5_8_repair1_app_registration.py`
- `python -m unittest tests.unit.test_0_1_5_7_unified_desktop tests.unit.test_0_1_5_8_installed_app_discovery -v`
- `python -m unittest discover -s tests -q`
- `npm run desktop:check`
- `npm run desktop:build`
- `python .\scripts\app_inventory_probe.py Discord Spotify`
- `python .\scripts\realtime_ab.py mini-overlap-luna-trim-guided-universal-apps`

Standard five, in order: 'Hey Jarvis, what is seventeen times twenty-three?', 'What planet is called the Red Planet?', 'What is the capital of France?', 'How are you doing today?', 'Thanks Jarvis, that\'s all.' Fast speech, naturalness, wake/sleep must remain unchanged.

Then ask: 'Jarvis, open Discord.' (Discord desktop app); 'Launch Spotify.' (Spotify desktop app); 'Please open File Explorer.'; 'Open YouTube.'; 'Search YouTube for Sidemen.'; 'Don\'t open Discord.'; 'Open Discord and Spotify.' (NO partial launch); 'Thanks Jarvis, that\'s all.'

For successful apps, check visible app window yourself; Core still reports Windows handoff rather than verified window presence. If Spotify still fails, share output from the read-only app inventory probe. The scan waits up to 12 seconds asynchronously on first start, not each conversation turn.

Do not clean patch/backup or commit before live acceptance; if failed, use existing checkpoint or share logs.
