"""0.1.3 Repair7: untrusted Unicode cannot crash Windows terminal logs."""
from __future__ import annotations
import io
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch
from apps.desktop_alpha import _terminal_chat_text, _configure_terminal_output

ROOT=Path(__file__).resolve().parents[2]
HOST=(ROOT/'apps/desktop_alpha.py').read_text(encoding='utf-8')

class LegacyConsole:
    encoding='cp1252'

class Utf8Console:
    encoding='utf-8'

class ConsoleTraceTests(unittest.TestCase):
    def test_cp1252_escapes_unencodable_chinese_from_voice(self):
        spoken='Jarvis, 我 need help. Thanks, Jervis! 😀'
        with patch('apps.desktop_alpha.sys.stdout',LegacyConsole()):
            rendered=_terminal_chat_text(spoken)
        rendered.encode('cp1252', errors='strict')
        self.assertIn(r'\u6211',rendered)
        self.assertIn(r'\ud83d\ude00',rendered)
        self.assertEqual(json.loads(rendered),spoken)

    def test_cp1252_trace_preserves_accents_and_single_line(self):
        with patch('apps.desktop_alpha.sys.stdout',LegacyConsole()):
            rendered=_terminal_chat_text('café   我\n[31moutput')
        rendered.encode('cp1252', errors='strict')
        self.assertIn(r'\u6211',rendered)
        self.assertEqual(json.loads(rendered),'café 我 [31moutput')
        self.assertNotIn('\n', json.loads(rendered))

    def test_utf8_preserves_natural_unicode_for_readable_logs(self):
        with patch('apps.desktop_alpha.sys.stdout',Utf8Console()):
            rendered=_terminal_chat_text('你好 — Jarvis 😀')
        self.assertIn('你好', rendered)
        self.assertEqual(json.loads(rendered),'你好 — Jarvis 😀')

    def test_long_output_is_bounded_even_on_legacy_console(self):
        with patch('apps.desktop_alpha.sys.stdout',LegacyConsole()):
            rendered=_terminal_chat_text('我'*900,limit=60)
        rendered.encode('cp1252', errors='strict')
        self.assertEqual(len(json.loads(rendered)),60)
        self.assertTrue(json.loads(rendered).endswith('…'))

    def test_other_console_logs_never_crash_from_provider_unicode(self):
        stdout_buffer=io.BytesIO()
        stderr_buffer=io.BytesIO()
        with (io.TextIOWrapper(stdout_buffer,encoding='cp1252',errors='strict') as output,
              io.TextIOWrapper(stderr_buffer,encoding='cp1252',errors='strict') as errors):
            with patch('apps.desktop_alpha.sys.stdout',output), patch('apps.desktop_alpha.sys.stderr',errors):
                _configure_terminal_output()
                self.assertEqual(output.errors,'backslashreplace')
                self.assertEqual(errors.errors,'backslashreplace')
                print('Provider said 我 😀',file=output,flush=True)
                print('Error says 我 😀',file=errors,flush=True)
                self.assertIn(r'\u6211',stdout_buffer.getvalue().decode('cp1252'))
                self.assertIn(r'\u6211',stderr_buffer.getvalue().decode('cp1252'))

    def test_websocket_trace_runs_before_core_but_only_print_representation_changes(self):
        self.assertIn('_configure_terminal_output()\n    args = parser().parse_args()',HOST)
        self.assertIn("text={_terminal_chat_text(message.get('text'))}",HOST)
        self.assertIn('self._luna.transcript(turn, str(message.get("text") or ""))',HOST)
        self.assertIn('self._bench.on_user(turn, str(message.get("text") or ""))',HOST)

if __name__ == '__main__':unittest.main()
