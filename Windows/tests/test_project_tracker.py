import copy
import json
import unittest
from unittest.mock import patch
from urllib.parse import unquote

from bluey import project_tracker as p


class Response:
    status_code = 200
    def __init__(self, value):
        self.value = value
    def json(self):
        return self.value


class Sheet:
    def __init__(self):
        self.tabs = {tab: [headers.copy()] for tab, headers in p.HEADERS.items()}
        self.writes = []
        self.fail = False
        self.bad_readback = False
        self.activity_fail = False
    def request(self, method, url, **kwargs):
        if self.fail:
            raise RuntimeError('secret-token-must-not-escape')
        import re
        name = unquote(url.rsplit('/', 1)[-1])
        match = re.fullmatch(r"'([^']+)'!A(\d+):[A-Z](\d+)", name)
        tab, start, end = match.group(1), int(match.group(2)), int(match.group(3))
        if method == 'PUT':
            if self.activity_fail and tab == 'Activity':
                raise RuntimeError('activity error')
            self.writes.append((tab, kwargs))
            while len(self.tabs[tab]) < start:
                self.tabs[tab].append([])
            self.tabs[tab][start - 1] = copy.deepcopy(kwargs['json']['values'][0])
            return Response({})
        if self.bad_readback and start > 1:
            return Response({'values': [['wrong']]})
        return Response({'values': copy.deepcopy(self.tabs[tab][start-1:end])})


class TrackerTests(unittest.TestCase):
    def setUp(self):
        self.sheet = Sheet()
        self.tracker = p.Tracker(self.sheet, 'test_sheet')
    def project(self):
        return self.tracker.upsert('Projects', {'Project ID': 'P1', 'Project': 'Bluey', 'Owner': 'Scott'})
    def test_create_raw_readback_activity_and_retry(self):
        result = self.tracker.upsert('Projects', {'Project ID': 'P1', 'Project': '=IMPORTXML("x")'})
        self.assertEqual(result['status'], 'saved')
        self.assertTrue(all(options['params']['valueInputOption'] == 'RAW' for _, options in self.sheet.writes))
        self.assertEqual(len(self.sheet.tabs['Activity']), 2)
        self.assertEqual(self.tracker.upsert('Projects', {'Project ID': 'P1', 'Project': '=IMPORTXML("x")'})['status'], 'unchanged')
        self.assertEqual(len(self.sheet.writes), 2)
    def test_patch_preserves_unspecified_fields(self):
        self.project()
        result = self.tracker.upsert('Projects', {'Project ID': 'P1', 'Status': 'Active'})
        self.assertEqual(result['record']['Owner'], 'Scott')
        self.assertEqual(result['record']['Project'], 'Bluey')
    def test_relocates_id_after_manual_row_move(self):
        self.project()
        self.sheet.tabs['Projects'].insert(1, ['P2', 'Other'])
        self.tracker.upsert('Projects', {'Project ID': 'P1', 'Status': 'Done'})
        self.assertEqual(self.sheet.tabs['Projects'][2][3], 'Done')
        self.assertEqual(self.sheet.tabs['Projects'][1][0], 'P2')
    def test_duplicate_ids_block_writes(self):
        self.project()
        self.sheet.tabs['Projects'].append(self.sheet.tabs['Projects'][1].copy())
        count = len(self.sheet.writes)
        with self.assertRaisesRegex(p.TrackerError, 'duplicate'):
            self.tracker.upsert('Projects', {'Project ID': 'P1', 'Status': 'Done'})
        self.assertEqual(len(self.sheet.writes), count)
    def test_invalid_headers_any_tab_blocks(self):
        self.sheet.tabs['Notes'][0][0] = 'Wrong'
        with self.assertRaisesRegex(p.TrackerError, 'headers'):
            self.project()
        self.assertFalse(self.sheet.writes)
    def test_task_requires_project(self):
        with self.assertRaisesRegex(p.TrackerError, 'existing project'):
            self.tracker.upsert('Tasks', {'Task ID': 'T1', 'Project ID': 'P1', 'Task': 'Test'})
        self.project()
        self.assertEqual(self.tracker.upsert('Tasks', {'Task ID': 'T1', 'Project ID': 'P1', 'Task': 'Test'})['status'], 'saved')
    def test_notes_idempotent_and_references(self):
        self.project()
        record = {'Note ID': 'N1', 'Project ID': 'P1', 'Note': 'Test'}
        self.tracker.upsert('Notes', record)
        self.assertEqual(self.tracker.upsert('Notes', record)['status'], 'unchanged')
        with self.assertRaisesRegex(p.TrackerError, 'different content'):
            self.tracker.upsert('Notes', dict(record, Note='Changed'))
        with self.assertRaisesRegex(p.TrackerError, 'Task ID'):
            self.tracker.upsert('Notes', {'Note ID': 'N2', 'Project ID': 'P1', 'Task ID': 'T99', 'Note': 'Test'})
    def test_validation(self):
        for record in [{'Project ID': '=x', 'Project': 'Test'}, {'Project ID': 'P1', 'Project': 'Test', 'Due date': '2026-02-30'}, {'Project ID': 'P1', 'Project': 'Test', 'Updated at': 'x'}, {'Project ID': 'P1', 'Project': 1}]:
            with self.assertRaises(p.TrackerError):
                self.tracker.upsert('Projects', record)
        self.assertFalse(self.sheet.writes)
    def test_http_failure_sanitized(self):
        self.sheet.fail = True
        with self.assertRaisesRegex(p.TrackerError, 'No automatic write retry') as error:
            self.project()
        self.assertNotIn('secret-token', str(error.exception))
    def test_failed_readback_stops_activity(self):
        self.sheet.bad_readback = True
        with self.assertRaisesRegex(p.TrackerError, 'readback'):
            self.project()
        self.assertEqual(len(self.sheet.writes), 1)
    def test_partial_activity_reported(self):
        self.sheet.activity_fail = True
        self.assertEqual(self.project()['status'], 'saved_activity_unverified')
    def test_overflow_explicit(self):
        self.sheet.tabs['Projects'].extend([[str(n), 'Project'] for n in range(p.MAX_ROWS + 1)])
        with self.assertRaisesRegex(p.TrackerError, 'exceeds'):
            self.tracker.rows('Projects')
    def test_url_restriction(self):
        self.assertEqual(p.sheet_id('https://docs.google.com/spreadsheets/d/abc123/edit#gid=0'), 'abc123')
        for url in ['https://evil.example/spreadsheets/d/abc', 'https://docs.google.com.evil/spreadsheets/d/abc']:
            with self.assertRaises(p.TrackerError):
                p.sheet_id(url)
    def test_dispatch_rejects_arbitrary_sheet(self):
        result = json.loads(p.dispatch('list_projects', {'spreadsheet_id': 'evil'}))
        self.assertIn('error', result)
    def test_dispatch_connected_crud(self):
        with patch.object(p, 'authorized_session', return_value=self.sheet), patch.object(p, 'sheet_url', return_value='https://docs.google.com/spreadsheets/d/test_sheet/edit'):
            saved = json.loads(p.dispatch('upsert_project', {'record': {'Project ID': 'P1', 'Project': 'Bluey'}}))
            self.assertEqual(saved['status'], 'saved')
            listed = json.loads(p.dispatch('list_projects', {}))
            self.assertEqual(listed['records'][0]['Project'], 'Bluey')
            record = json.loads(p.dispatch('get_project', {'id': 'P1'}))
            self.assertEqual(record['record']['Project ID'], 'P1')
    def test_oversized_write_reports_saved_not_error(self):
        record = {'Project ID': 'P1', 'Project': 'Bluey', 'Client': 'x'*10000, 'Owner': 'x'*10000, 'Blocker': 'x'*10000}
        with patch.object(p, 'authorized_session', return_value=self.sheet), patch.object(p, 'sheet_url', return_value='https://docs.google.com/spreadsheets/d/test_sheet/edit'):
            result = json.loads(p.dispatch('upsert_project', {'record': record}))
        self.assertEqual(result['status'], 'saved')
        self.assertEqual(result['record_id'], 'P1')
    def test_settings_merge(self):
        import tempfile
        from pathlib import Path
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'settings.json'
            path.write_text('{"tray_setting": true}')
            with patch.object(p, 'settings_path', return_value=path):
                p.save_settings(project_sheet_url='url')
            self.assertEqual(json.loads(path.read_text())['tray_setting'], True)

if __name__ == '__main__':
    unittest.main()

