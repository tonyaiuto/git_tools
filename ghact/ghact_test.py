"""Tests for ghact.py (CLI and PR ref parsing)."""

import signal
import unittest
from unittest.mock import patch

import ghact


# ── ghact._parse_pr_ref ───────────────────────────────────────────────────────

class TestParsePrRef(unittest.TestCase):

    def test_plain_number(self):
        self.assertEqual(ghact._parse_pr_ref('42', None), (42, None))

    def test_plain_number_with_repo(self):
        self.assertEqual(ghact._parse_pr_ref('42', 'owner/repo'), (42, 'owner/repo'))

    def test_url_extracts_pr_and_repo(self):
        self.assertEqual(
            ghact._parse_pr_ref('https://github.com/owner/repo/pull/42', None),
            (42, 'owner/repo'),
        )

    def test_url_repo_override_wins(self):
        self.assertEqual(
            ghact._parse_pr_ref('https://github.com/owner/repo/pull/42', 'other/repo'),
            (42, 'other/repo'),
        )

    def test_invalid_returns_none(self):
        self.assertEqual(ghact._parse_pr_ref('not-a-pr', None), (None, None))


# ── ghact main (CLI integration) ─────────────────────────────────────────────

class TestMain(unittest.TestCase):

    @patch('actions.add_label')
    def test_add_label_no_condition(self, mock_add):
        ghact.main(['42', 'add-label', 'my-label'])
        mock_add.assert_called_once_with(42, 'my-label', None)

    @patch('actions.add_comment')
    def test_add_comment(self, mock_comment):
        ghact.main(['10', 'add-comment', 'hello world'])
        mock_comment.assert_called_once_with(10, 'hello world', None)

    @patch('conditions.check_conditions', return_value=False)
    @patch('actions.add_label')
    def test_condition_not_met_skips_action(self, mock_add, mock_cond):
        ghact.main(['--if', 'approved', '42', 'add-label', 'lgtm'])
        mock_cond.assert_called_once_with('approved', 42, None)
        mock_add.assert_not_called()

    @patch('conditions.check_conditions', return_value=True)
    @patch('actions.add_label')
    def test_condition_met_runs_action(self, mock_add, mock_cond):
        ghact.main(['--if', 'approved', '42', 'add-label', 'lgtm'])
        mock_add.assert_called_once_with(42, 'lgtm', None)

    @patch('actions.add_label')
    def test_repo_forwarded(self, mock_add):
        ghact.main(['--repo', 'owner/repo', '5', 'add-label', 'foo'])
        mock_add.assert_called_once_with(5, 'foo', 'owner/repo')

    @patch('actions.merge')
    def test_url_extracts_repo(self, mock_merge):
        ghact.main(['https://github.com/owner/repo/pull/42', 'merge'])
        mock_merge.assert_called_once_with(42, 'owner/repo')

    @patch('actions.merge')
    def test_repo_flag_overrides_url(self, mock_merge):
        ghact.main(['--repo', 'other/repo', 'https://github.com/owner/repo/pull/42', 'merge'])
        mock_merge.assert_called_once_with(42, 'other/repo')

    @patch('actions.ready')
    def test_ready_command(self, mock_ready):
        ghact.main(['42', 'ready'])
        mock_ready.assert_called_once_with(42, None)

    @patch('actions.run_gh')
    def test_gh_passthrough(self, mock_run):
        ghact.main(['42', 'gh', 'pr', 'view', '--json', 'title'])
        mock_run.assert_called_once_with(['pr', 'view', '--json', 'title'], None)

    @patch('actions.run_gh')
    def test_gh_passthrough_injects_repo_from_url(self, mock_run):
        ghact.main(['https://github.com/owner/repo/pull/42', 'gh', 'pr', 'view'])
        mock_run.assert_called_once_with(['pr', 'view'], 'owner/repo')


# ── --at / --after scheduling ────────────────────────────────────────────────

class TestScheduling(unittest.TestCase):

    @patch('timing.sleep_until')
    @patch('actions.merge')
    def test_at_calls_sleep_then_action(self, mock_merge, mock_sleep):
        ghact.main(['--at', '3pm', '42', 'merge'])
        mock_sleep.assert_called_once()
        target = mock_sleep.call_args[0][0]
        self.assertEqual(target.hour, 15)
        self.assertEqual(target.minute, 0)
        mock_merge.assert_called_once_with(42, None)

    @patch('timing.sleep_until')
    @patch('actions.merge')
    def test_after_calls_sleep_then_action(self, mock_merge, mock_sleep):
        ghact.main(['--after', '2h', '42', 'merge'])
        mock_sleep.assert_called_once()
        mock_merge.assert_called_once_with(42, None)

    @patch('timing.sleep_until')
    @patch('actions.merge')
    def test_no_timing_flag_skips_sleep(self, mock_merge, mock_sleep):
        ghact.main(['42', 'merge'])
        mock_sleep.assert_not_called()
        mock_merge.assert_called_once()

    @patch('timing.sleep_until')
    @patch('actions.merge')
    def test_at_verbose_forwarded(self, mock_merge, mock_sleep):
        ghact.main(['-v', '--at', '3pm', '42', 'merge'])
        _, kwargs = mock_sleep.call_args
        self.assertTrue(kwargs.get('verbose'))


# ── real sleep integration ────────────────────────────────────────────────────

class TestRealSleep(unittest.TestCase):
    """Integration test that exercises the actual sleep path end-to-end."""

    @patch('actions.merge')
    def test_after_5s_completes_and_acts(self, mock_merge):
        def _timeout(signum, frame):
            raise TimeoutError('--after 5s took longer than 8 seconds')

        signal.signal(signal.SIGALRM, _timeout)
        signal.alarm(8)
        try:
            ghact.main(['--after', '5s', '42', 'merge'])
        finally:
            signal.alarm(0)

        mock_merge.assert_called_once_with(42, None)


# ── pr subcommand ─────────────────────────────────────────────────────────────

class TestPrCommand(unittest.TestCase):

    @patch('conditions.check_conditions', return_value=True)
    def test_condition_true_exits_0(self, mock_cond):
        with self.assertRaises(SystemExit) as cm:
            ghact.main(['--if', 'approved', '42', 'pr'])
        self.assertEqual(cm.exception.code, 0)

    @patch('conditions.check_conditions', return_value=False)
    def test_condition_false_exits_1(self, mock_cond):
        with self.assertRaises(SystemExit) as cm:
            ghact.main(['--if', 'approved', '42', 'pr'])
        self.assertEqual(cm.exception.code, 1)

    @patch('conditions.check_conditions', return_value=True)
    def test_no_output(self, mock_cond):
        import io
        with self.assertRaises(SystemExit):
            with patch('sys.stdout', new_callable=io.StringIO) as mock_out, \
                 patch('sys.stderr', new_callable=io.StringIO) as mock_err:
                ghact.main(['--if', 'approved', '42', 'pr'])
                self.assertEqual(mock_out.getvalue(), '')
                self.assertEqual(mock_err.getvalue(), '')

    def test_missing_condition_is_error(self):
        with self.assertRaises(SystemExit) as cm:
            ghact.main(['42', 'pr'])
        self.assertNotEqual(cm.exception.code, 0)


if __name__ == '__main__':
    unittest.main()
