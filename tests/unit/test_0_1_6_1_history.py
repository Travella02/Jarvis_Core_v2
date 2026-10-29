"""0.1.6.1 local history durability, owner isolation and integrity regressions."""
from __future__ import annotations

from pathlib import Path
import tempfile
import unittest

from core.memory.history import ConversationHistoryStore, MAX_TEXT


class LocalHistoryTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path=Path(self.tmp.name)/'history.sqlite3'
        self.store=ConversationHistoryStore(self.path,owner_id='alice')
        self.sid=self.store.start_session(device_id='win-desktop',model='mini')

    def test_session_created_durably(self):
        self.assertTrue(self.path.exists())
        self.assertEqual(len(self.store.sessions()),1)
        self.assertEqual(self.store.sessions()[0]['device_id'],'win-desktop')

    def test_user_and_assistant_survive_restart(self):
        utterance='Hello Jarvis, remember C++ 🧠 and punctuation!'
        self.store.append(self.sid,turn=1,role='user',source='voice',text=utterance,status='transcribed')
        self.store.append(self.sid,turn=1,role='assistant',source='overlap_realtime',text='Hello there!',status='reported_output')
        reopened=ConversationHistoryStore(self.path,owner_id='alice')
        rows=reopened.entries(self.sid)
        self.assertEqual([r['text'] for r in rows],[utterance,'Hello there!'])
        self.assertEqual([r['role'] for r in rows],['user','assistant'])

    def test_exact_duplicate_is_idempotent(self):
        self.assertTrue(self.store.append(self.sid,turn=5,role='assistant',source='core',text='Okay'))
        self.assertFalse(self.store.append(self.sid,turn=5,role='assistant',source='realtime',text='Okay'))
        self.assertEqual(len(self.store.entries(self.sid)),1)

    def test_legitimate_different_replies_remain(self):
        self.store.append(self.sid,turn=5,role='assistant',source='core',text='Part one')
        self.store.append(self.sid,turn=5,role='assistant',source='core',text='Part two')
        self.assertEqual(len(self.store.entries(self.sid)),2)

    def test_same_words_different_turns_remain(self):
        for turn in (1,2):
            self.store.append(self.sid,turn=turn,role='user',source='typed',text='Hi')
        self.assertEqual(len(self.store.entries(self.sid)),2)

    def test_action_outcomes_preserve_distinct_status(self):
        self.store.append(self.sid,turn=8,role='action',source='browser',text='Browser action outcome: timeout',status='failed')
        self.store.append(self.sid,turn=8,role='action',source='browser',text='Browser action outcome: selected_video_same_tab',status='completed')
        self.assertEqual(len(self.store.entries(self.sid)),2)

    def test_search_phrase_and_keyword(self):
        self.store.append(self.sid,turn=1,role='user',source='voice',text='Find videos from the Sidemen')
        self.store.append(self.sid,turn=2,role='user',source='voice',text='No videos please')
        self.assertEqual(len(self.store.search('Sidemen')),1)
        self.assertEqual(len(self.store.search('videos')),2)
        self.assertEqual(len(self.store.search('videos from the')),1)

    def test_search_special_query_does_not_inject(self):
        self.store.append(self.sid,turn=1,role='user',source='voice',text='C++ and SQLite')
        self.assertEqual(len(self.store.search('C++')),1)
        self.assertEqual(self.store.search('" OR 1=1 --'),[])

    def test_sessions_are_isolated_by_owner(self):
        self.store.append(self.sid,turn=1,role='user',source='voice',text='Private secret')
        other=ConversationHistoryStore(self.path,owner_id='bob')
        self.assertEqual(other.sessions(),[])
        self.assertEqual(other.entries(self.sid),[])
        self.assertEqual(other.search('Private'),[])
        with self.assertRaises(ValueError):
            other.append(self.sid,turn=2,role='user',source='typed',text='Oops')
        self.assertFalse(other.delete_session(self.sid))
        self.assertEqual(len(self.store.entries(self.sid)),1)

    def test_delete_session_removes_entries_and_index(self):
        self.store.append(self.sid,turn=1,role='user',source='voice',text='Deletion test token')
        self.assertTrue(self.store.delete_session(self.sid))
        self.assertEqual(self.store.entries(self.sid),[])
        self.assertEqual(self.store.search('Deletion test token'),[])
        self.assertFalse(self.store.delete_session(self.sid))

    def test_end_session_is_idempotent(self):
        self.store.end_session(self.sid)
        previous=self.store.sessions()[0]['ended_at']
        self.store.end_session(self.sid)
        self.assertEqual(self.store.sessions()[0]['ended_at'],previous)

    def test_invalid_roles_rejected(self):
        with self.assertRaises(ValueError):
            self.store.append(self.sid,turn=1,role='system',source='voice',text='hidden provider prompt')

    def test_empty_entries_not_saved(self):
        self.assertFalse(self.store.append(self.sid,turn=1,role='user',source='voice',text='  '))
        self.assertEqual(self.store.entries(self.sid),[])

    def test_no_silent_truncation(self):
        with self.assertRaises(ValueError):
            self.store.append(self.sid,turn=1,role='user',source='voice',text='x'*(MAX_TEXT+1))

    def test_bad_configuration_rejected(self):
        with self.assertRaises(ValueError):
            ConversationHistoryStore.from_environment(Path(self.tmp.name),{'JARVIS_CHAT_HISTORY_ENABLED':'maybe'})

    def test_opt_out_does_not_create_new_database(self):
        empty_path=Path(self.tmp.name)/'unused'
        self.assertIsNone(ConversationHistoryStore.from_environment(empty_path,{'JARVIS_CHAT_HISTORY_ENABLED':'0'}))
        self.assertFalse(empty_path.exists())

    def test_path_configuration_is_relative_to_project(self):
        root=Path(self.tmp.name)
        store=ConversationHistoryStore.from_environment(root,{'JARVIS_CHAT_HISTORY_DB':'private/history.sqlite3'})
        self.assertIsNotNone(store)
        self.assertEqual(store.path, root/'private'/'history.sqlite3')

    def test_unfamiliar_session_cannot_be_spoofed(self):
        with self.assertRaises(ValueError):
            self.store.append('unknown',turn=1,role='user',source='typed',text='Hello')

    def test_list_limit_and_order(self):
        self.assertEqual(len(self.store.sessions(limit=1)),1)
        with self.assertRaises(ValueError): self.store.sessions(limit=0)


if __name__=='__main__':
    unittest.main()
