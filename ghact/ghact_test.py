"""Tests for ghact."""

import json
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

    def test_silent_by_default(self):
        import io
        past = datetime.now() - timedelta(seconds=1)
        with patch('sys.stderr', new_callable=io.StringIO) as mock_err:
            timing.sleep_until(past)
        self.assertEqual(mock_err.getvalue(), '')

    @patch('time.sleep')
    def test_verbose_prints(self, mock_sleep):
        import io
        now = datetime.now()
        future = now + timedelta(seconds=60)
        # First now() call: before target (so verbose message prints).
        # Second now() call (in the while loop): past target so loop exits.
        with patch('timing.datetime') as mock_dt:
            mock_dt.now.side_effect = [now, future + timedelta(seconds=1)]
            with patch('sys.stderr', new_callable=io.StringIO) as mock_err:
                timing.sleep_until(future, verbose=True)
        self.assertIn('Sleeping until', mock_err.getvalue())


# ── conditions._check_one ────────────────────────────────────────────────────

class TestCheckOne(unittest.TestCase):

    @patch('conditions._gh')
    def test_approved_true(self, mock_gh):
        mock_gh.return_value = {'reviewDecision': 'APPROVED'}
        self.assertTrue(conditions._check_one('approved', 42, None))
        mock_gh.assert_called_once_with(
            ['pr', 'view', '42', '--json', 'reviewDecision'], None
        )

    @patch('conditions._gh')
    def test_approved_false(self, mock_gh):
        mock_gh.return_value = {'reviewDecision': 'REVIEW_REQUIRED'}
        self.assertFalse(conditions._check_one('approved', 42, None))

    @patch('conditions._gh')
    def test_unapproved_true(self, mock_gh):
        mock_gh.return_value = {'reviewDecision': 'REVIEW_REQUIRED'}
        self.assertTrue(conditions._check_one('unapproved', 42, None))

    @patch('conditions._gh')
    def test_unapproved_false_when_approved(self, mock_gh):
        mock_gh.return_value = {'reviewDecision': 'APPROVED'}
        self.assertFalse(conditions._check_one('unapproved', 42, None))

    @patch('conditions._gh')
    def test_ci_passing_all_success(self, mock_gh):
        mock_gh.return_value = {'statusCheckRollup': [
            {'conclusion': 'SUCCESS'},
            {'conclusion': 'SKIPPED'},
        ]}
        self.assertTrue(conditions._check_one('passing', 42, None))

    @patch('conditions._gh')
    def test_ci_passing_one_failure(self, mock_gh):
        mock_gh.return_value = {'statusCheckRollup': [
            {'conclusion': 'SUCCESS'},
            {'conclusion': 'FAILURE'},
        ]}
        self.assertFalse(conditions._check_one('passing', 42, None))

    @patch('conditions._gh')
    def test_ci_passing_no_checks_is_false(self, mock_gh):
        mock_gh.return_value = {'statusCheckRollup': []}
        self.assertFalse(conditions._check_one('passing', 42, None))

    @patch('conditions._gh')
    def test_draft(self, mock_gh):
        mock_gh.return_value = {'isDraft': True}
        self.assertTrue(conditions._check_one('draft', 42, None))

    @patch('conditions._gh')
    def test_ready(self, mock_gh):
        mock_gh.return_value = {'isDraft': False}
        self.assertTrue(conditions._check_one('ready', 42, None))

    @patch('conditions._has_unresolved_threads', return_value=False)
    def test_no_unresolved_threads_true(self, mock_threads):
        self.assertTrue(conditions._check_one('no-unresolved-threads', 42, None))
        mock_threads.assert_called_once_with(42, None)

    @patch('conditions._has_unresolved_threads', return_value=True)
    def test_no_unresolved_threads_false(self, mock_threads):
        self.assertFalse(conditions._check_one('no-unresolved-threads', 42, None))

    def test_unknown_condition_raises(self):
        with self.assertRaises(ValueError):
            conditions._check_one('bogus', 42, None)

    @patch('conditions._gh')
    def test_repo_forwarded(self, mock_gh):
        mock_gh.return_value = {'reviewDecision': 'APPROVED'}
        conditions._check_one('approved', 7, 'owner/repo')
        mock_gh.assert_called_once_with(
            ['pr', 'view', '7', '--json', 'reviewDecision'], 'owner/repo'
        )


# ── conditions.check_conditions ──────────────────────────────────────────────

class TestCheckConditions(unittest.TestCase):

    @patch('conditions._check_one', return_value=True)
    def test_single_condition_true(self, mock_one):
        self.assertTrue(conditions.check_conditions('approved', 42))
        mock_one.assert_called_once_with('approved', 42, None)

    @patch('conditions._check_one', return_value=False)
    def test_single_condition_false(self, mock_one):
        self.assertFalse(conditions.check_conditions('approved', 42))

    @patch('conditions._check_one', return_value=True)
    def test_multiple_all_true(self, mock_one):
        self.assertTrue(conditions.check_conditions('approved,passing,ready', 42))
        self.assertEqual(mock_one.call_count, 3)

    @patch('conditions._check_one')
    def test_multiple_short_circuits_on_false(self, mock_one):
        mock_one.side_effect = [True, False]
        self.assertFalse(conditions.check_conditions('approved,passing,ready', 42))
        self.assertEqual(mock_one.call_count, 2)

    @patch('conditions._check_one')
    def test_whitespace_around_commas(self, mock_one):
        mock_one.return_value = True
        conditions.check_conditions('approved, passing', 42)
        mock_one.assert_any_call('approved', 42, None)
        mock_one.assert_any_call('passing', 42, None)

    @patch('conditions._check_one')
    def test_unknown_condition_raises(self, mock_one):
        mock_one.side_effect = ValueError('Unknown condition')
        with self.assertRaises(ValueError):
            conditions.check_conditions('bogus', 42)



# ── conditions._has_unresolved_threads ───────────────────────────────────────

class TestHasUnresolvedThreads(unittest.TestCase):

    def _graphql_response(self, threads):
        return json.dumps({
            'data': {'repository': {'pullRequest': {
                'reviewThreads': {'nodes': threads}
            }}}
        })

    @patch('subprocess.run')
    @patch('conditions._repo_owner_name', return_value=('owner', 'repo'))
    def test_no_threads(self, mock_repo, mock_run):
        mock_run.return_value = _FakeResult(0, self._graphql_response([]))
        self.assertFalse(conditions._has_unresolved_threads(42, 'owner/repo'))

    @patch('subprocess.run')
    @patch('conditions._repo_owner_name', return_value=('owner', 'repo'))
    def test_all_resolved(self, mock_repo, mock_run):
        mock_run.return_value = _FakeResult(0, self._graphql_response([
            {'isResolved': True},
            {'isResolved': True},
        ]))
        self.assertFalse(conditions._has_unresolved_threads(42, 'owner/repo'))

    @patch('subprocess.run')
    @patch('conditions._repo_owner_name', return_value=('owner', 'repo'))
    def test_one_unresolved(self, mock_repo, mock_run):
        mock_run.return_value = _FakeResult(0, self._graphql_response([
            {'isResolved': True},
            {'isResolved': False},
        ]))
        self.assertTrue(conditions._has_unresolved_threads(42, 'owner/repo'))

    @patch('subprocess.run')
    @patch('conditions._repo_owner_name', return_value=('owner', 'repo'))
    def test_graphql_failure_raises(self, mock_repo, mock_run):
        mock_run.return_value = _FakeResult(1, '', 'some error')
        with self.assertRaises(RuntimeError):
            conditions._has_unresolved_threads(42, 'owner/repo')


class _FakeResult:
    def __init__(self, returncode, stdout='', stderr=''):
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr


# ── ghact._parse_pr_ref ───────────────────────────────────────────────────────

class TestParsePrRef(unittest.TestCase):

    def setUp(self):
        import ghact
        self.parse = ghact._parse_pr_ref

    def test_plain_number(self):
        self.assertEqual(self.parse('42', None), (42, None))

    def test_plain_number_with_repo(self):
        self.assertEqual(self.parse('42', 'owner/repo'), (42, 'owner/repo'))

    def test_url_extracts_pr_and_repo(self):
        self.assertEqual(
            self.parse('https://github.com/owner/repo/pull/42', None),
            (42, 'owner/repo'),
        )

    def test_url_repo_override_wins(self):
        self.assertEqual(
            self.parse('https://github.com/owner/repo/pull/42', 'other/repo'),
            (42, 'other/repo'),
        )

    def test_invalid_returns_none(self):
        self.assertEqual(self.parse('not-a-pr', None), (None, None))


# ── ghact main (CLI integration) ─────────────────────────────────────────────

class TestMain(unittest.TestCase):

    @patch('actions.add_label')
    def test_add_label_no_condition(self, mock_add):
        import ghact
        ghact.main(['42', 'add-label', 'my-label'])
        mock_add.assert_called_once_with(42, 'my-label', None)

    @patch('actions.add_comment')
    def test_add_comment(self, mock_comment):
        import ghact
        ghact.main(['10', 'add-comment', 'hello world'])
        mock_comment.assert_called_once_with(10, 'hello world', None)

    @patch('conditions.check_conditions', return_value=False)
    @patch('actions.add_label')
    def test_condition_not_met_skips_action(self, mock_add, mock_cond):
        import ghact
        ghact.main(['--if', 'approved', '42', 'add-label', 'lgtm'])
        mock_cond.assert_called_once_with('approved', 42, None)
        mock_add.assert_not_called()

    @patch('conditions.check_conditions', return_value=True)
    @patch('actions.add_label')
    def test_condition_met_runs_action(self, mock_add, mock_cond):
        import ghact
        ghact.main(['--if', 'approved', '42', 'add-label', 'lgtm'])
        mock_add.assert_called_once_with(42, 'lgtm', None)

    @patch('actions.add_label')
    def test_repo_forwarded(self, mock_add):
        import ghact
        ghact.main(['--repo', 'owner/repo', '5', 'add-label', 'foo'])
        mock_add.assert_called_once_with(5, 'foo', 'owner/repo')

    @patch('actions.merge')
    def test_url_extracts_repo(self, mock_merge):
        import ghact
        ghact.main(['https://github.com/owner/repo/pull/42', 'merge'])
        mock_merge.assert_called_once_with(42, 'owner/repo')

    @patch('actions.merge')
    def test_repo_flag_overrides_url(self, mock_merge):
        import ghact
        ghact.main(['--repo', 'other/repo', 'https://github.com/owner/repo/pull/42', 'merge'])
        mock_merge.assert_called_once_with(42, 'other/repo')

    @patch('actions.ready')
    def test_ready_command(self, mock_ready):
        import ghact
        ghact.main(['42', 'ready'])
        mock_ready.assert_called_once_with(42, None)

    @patch('actions.run_gh')
    def test_gh_passthrough(self, mock_run):
        import ghact
        ghact.main(['42', 'gh', 'pr', 'view', '--json', 'title'])
        mock_run.assert_called_once_with(['pr', 'view', '--json', 'title'], None)

    @patch('actions.run_gh')
    def test_gh_passthrough_injects_repo_from_url(self, mock_run):
        import ghact
        ghact.main(['https://github.com/owner/repo/pull/42', 'gh', 'pr', 'view'])
        mock_run.assert_called_once_with(['pr', 'view'], 'owner/repo')


# ── pr subcommand ─────────────────────────────────────────────────────────────

class TestPrCommand(unittest.TestCase):

    @patch('conditions.check_conditions', return_value=True)
    def test_condition_true_exits_0(self, mock_cond):
        import ghact
        with self.assertRaises(SystemExit) as cm:
            ghact.main(['--if', 'approved', '42', 'pr'])
        self.assertEqual(cm.exception.code, 0)

    @patch('conditions.check_conditions', return_value=False)
    def test_condition_false_exits_1(self, mock_cond):
        import ghact
        with self.assertRaises(SystemExit) as cm:
            ghact.main(['--if', 'approved', '42', 'pr'])
        self.assertEqual(cm.exception.code, 1)

    @patch('conditions.check_conditions', return_value=True)
    def test_no_output(self, mock_cond):
        import ghact
        import io
        with self.assertRaises(SystemExit):
            with patch('sys.stdout', new_callable=io.StringIO) as mock_out, \
                 patch('sys.stderr', new_callable=io.StringIO) as mock_err:
                ghact.main(['--if', 'approved', '42', 'pr'])
                self.assertEqual(mock_out.getvalue(), '')
                self.assertEqual(mock_err.getvalue(), '')

    def test_missing_condition_is_error(self):
        import ghact
        with self.assertRaises(SystemExit) as cm:
            ghact.main(['42', 'pr'])
        self.assertNotEqual(cm.exception.code, 0)


if __name__ == '__main__':
    unittest.main()
