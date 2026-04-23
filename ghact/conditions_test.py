"""Tests for conditions.py."""

import json
import unittest
from unittest.mock import patch

import conditions


class _FakeResult:
    def __init__(self, returncode, stdout='', stderr=''):
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr


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


if __name__ == '__main__':
    unittest.main()
