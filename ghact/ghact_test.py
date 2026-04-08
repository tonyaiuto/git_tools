"""Tests for ghact."""

import unittest
from datetime import datetime, timedelta
from unittest.mock import patch, call

import timing
import conditions
import actions


# ── timing.parse_at ───────────────────────────────────────────────────────────

class TestParseAt(unittest.TestCase):

    def _check(self, s, hour, minute):
        t = timing.parse_at(s)
        self.assertEqual(t.hour, hour)
        self.assertEqual(t.minute, minute)

    def test_hhmm_zero_padded(self):
        self._check('0300', 3, 0)

    def test_hhmm_afternoon(self):
        self._check('1430', 14, 30)

    def test_hh_colon_mm_24h(self):
        self._check('14:30', 14, 30)

    def test_hh_colon_mm_single_digit(self):
        self._check('2:05', 2, 5)

    def test_am(self):
        self._check('2:30am', 2, 30)

    def test_pm(self):
        self._check('2:30pm', 14, 30)

    def test_12am_is_midnight(self):
        self._check('12am', 0, 0)

    def test_12pm_is_noon(self):
        self._check('12pm', 12, 0)

    def test_whole_hour_pm(self):
        self._check('11pm', 23, 0)

    def test_whole_hour_am(self):
        self._check('3am', 3, 0)

    def test_invalid_raises(self):
        with self.assertRaises(ValueError):
            timing.parse_at('not-a-time')

    def test_invalid_letters_raises(self):
        with self.assertRaises(ValueError):
            timing.parse_at('noon')


# ── timing.parse_after ────────────────────────────────────────────────────────

class TestParseAfter(unittest.TestCase):

    def test_hours(self):
        self.assertEqual(timing.parse_after('2h'), timedelta(hours=2))

    def test_minutes(self):
        self.assertEqual(timing.parse_after('90m'), timedelta(minutes=90))

    def test_seconds(self):
        self.assertEqual(timing.parse_after('30s'), timedelta(seconds=30))

    def test_hours_and_minutes(self):
        self.assertEqual(timing.parse_after('1h30m'), timedelta(hours=1, minutes=30))

    def test_hours_minutes_seconds(self):
        self.assertEqual(timing.parse_after('1h30m20s'), timedelta(hours=1, minutes=30, seconds=20))

    def test_invalid_raises(self):
        with self.assertRaises(ValueError):
            timing.parse_after('invalid')

    def test_zero_raises(self):
        # An empty match is not useful
        with self.assertRaises(ValueError):
            timing.parse_after('')


# ── timing.sleep_until ────────────────────────────────────────────────────────

class TestSleepUntil(unittest.TestCase):

    @patch('time.sleep')
    def test_silent_by_default(self, mock_sleep):
        import io
        future = datetime.now() + timedelta(seconds=60)
        with patch('sys.stderr', new_callable=io.StringIO) as mock_err:
            timing.sleep_until(future)
        self.assertEqual(mock_err.getvalue(), '')

    @patch('time.sleep')
    def test_verbose_prints(self, mock_sleep):
        import io
        future = datetime.now() + timedelta(seconds=60)
        with patch('sys.stderr', new_callable=io.StringIO) as mock_err:
            timing.sleep_until(future, verbose=True)
        self.assertIn('Sleeping until', mock_err.getvalue())


# ── conditions.check_condition ───────────────────────────────────────────────

class TestCheckCondition(unittest.TestCase):

    @patch('conditions._gh')
    def test_approved_true(self, mock_gh):
        mock_gh.return_value = {'reviewDecision': 'APPROVED'}
        self.assertTrue(conditions.check_condition('approved', 42))
        mock_gh.assert_called_once_with(
            ['pr', 'view', '42', '--json', 'reviewDecision'], None
        )

    @patch('conditions._gh')
    def test_approved_false(self, mock_gh):
        mock_gh.return_value = {'reviewDecision': 'REVIEW_REQUIRED'}
        self.assertFalse(conditions.check_condition('approved', 42))

    @patch('conditions._gh')
    def test_unapproved_true(self, mock_gh):
        mock_gh.return_value = {'reviewDecision': 'REVIEW_REQUIRED'}
        self.assertTrue(conditions.check_condition('unapproved', 42))

    @patch('conditions._gh')
    def test_unapproved_false_when_approved(self, mock_gh):
        mock_gh.return_value = {'reviewDecision': 'APPROVED'}
        self.assertFalse(conditions.check_condition('unapproved', 42))

    @patch('conditions._gh')
    def test_ci_passing_all_success(self, mock_gh):
        mock_gh.return_value = {'statusCheckRollup': [
            {'conclusion': 'SUCCESS'},
            {'conclusion': 'SKIPPED'},
        ]}
        self.assertTrue(conditions.check_condition('passing', 42))

    @patch('conditions._gh')
    def test_ci_passing_one_failure(self, mock_gh):
        mock_gh.return_value = {'statusCheckRollup': [
            {'conclusion': 'SUCCESS'},
            {'conclusion': 'FAILURE'},
        ]}
        self.assertFalse(conditions.check_condition('passing', 42))

    @patch('conditions._gh')
    def test_ci_passing_no_checks_is_false(self, mock_gh):
        mock_gh.return_value = {'statusCheckRollup': []}
        self.assertFalse(conditions.check_condition('passing', 42))

    @patch('conditions._gh')
    def test_draft(self, mock_gh):
        mock_gh.return_value = {'isDraft': True}
        self.assertTrue(conditions.check_condition('draft', 42))

    @patch('conditions._gh')
    def test_ready(self, mock_gh):
        mock_gh.return_value = {'isDraft': False}
        self.assertTrue(conditions.check_condition('ready', 42))

    def test_unknown_condition_raises(self):
        with self.assertRaises(ValueError):
            conditions.check_condition('bogus', 42)

    @patch('conditions._gh')
    def test_repo_forwarded(self, mock_gh):
        mock_gh.return_value = {'reviewDecision': 'APPROVED'}
        conditions.check_condition('approved', 7, repo='owner/repo')
        mock_gh.assert_called_once_with(
            ['pr', 'view', '7', '--json', 'reviewDecision'], 'owner/repo'
        )


# ── ghact main (CLI integration) ─────────────────────────────────────────────

class TestMain(unittest.TestCase):

    @patch('actions.add_label')
    def test_add_label_no_condition(self, mock_add):
        import ghact
        ghact.main(['add-label', '42', 'my-label'])
        mock_add.assert_called_once_with(42, 'my-label', None)

    @patch('actions.add_comment')
    def test_add_comment(self, mock_comment):
        import ghact
        ghact.main(['add-comment', '10', 'hello world'])
        mock_comment.assert_called_once_with(10, 'hello world', None)

    @patch('conditions.check_condition', return_value=False)
    @patch('actions.add_label')
    def test_condition_not_met_skips_action(self, mock_add, mock_cond):
        import ghact
        ghact.main(['--if', 'approved', 'add-label', '42', 'lgtm'])
        mock_cond.assert_called_once_with('approved', 42, None)
        mock_add.assert_not_called()

    @patch('conditions.check_condition', return_value=True)
    @patch('actions.add_label')
    def test_condition_met_runs_action(self, mock_add, mock_cond):
        import ghact
        ghact.main(['--if', 'approved', 'add-label', '42', 'lgtm'])
        mock_add.assert_called_once_with(42, 'lgtm', None)

    @patch('actions.add_label')
    def test_repo_forwarded(self, mock_add):
        import ghact
        ghact.main(['--repo', 'owner/repo', 'add-label', '5', 'foo'])
        mock_add.assert_called_once_with(5, 'foo', 'owner/repo')


# ── pr subcommand ─────────────────────────────────────────────────────────────

class TestPrCommand(unittest.TestCase):

    @patch('conditions.check_condition', return_value=True)
    def test_condition_true_exits_0(self, mock_cond):
        import ghact
        with self.assertRaises(SystemExit) as cm:
            ghact.main(['--if', 'approved', 'pr', '42'])
        self.assertEqual(cm.exception.code, 0)

    @patch('conditions.check_condition', return_value=False)
    def test_condition_false_exits_1(self, mock_cond):
        import ghact
        with self.assertRaises(SystemExit) as cm:
            ghact.main(['--if', 'approved', 'pr', '42'])
        self.assertEqual(cm.exception.code, 1)

    @patch('conditions.check_condition', return_value=True)
    def test_no_output(self, mock_cond):
        import ghact
        import io
        with self.assertRaises(SystemExit):
            with patch('sys.stdout', new_callable=io.StringIO) as mock_out, \
                 patch('sys.stderr', new_callable=io.StringIO) as mock_err:
                ghact.main(['--if', 'approved', 'pr', '42'])
                self.assertEqual(mock_out.getvalue(), '')
                self.assertEqual(mock_err.getvalue(), '')

    def test_missing_condition_is_error(self):
        import ghact
        with self.assertRaises(SystemExit) as cm:
            ghact.main(['pr', '42'])
        self.assertNotEqual(cm.exception.code, 0)


if __name__ == '__main__':
    unittest.main()
