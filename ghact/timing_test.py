"""Tests for timing.py."""

import unittest
from datetime import date, datetime, timedelta
from unittest.mock import patch

import timing


# Freeze "now" so _future tests are deterministic regardless of when they run.
# 10:00:00 on a known date — safely midday, avoids edge cases at midnight.
_NOW = datetime(2026, 4, 22, 10, 0, 0)
_TODAY = _NOW.date()
_TOMORROW = (_NOW + timedelta(days=1)).date()


def _frozen_now(side_effects=None):
    """Patch timing.datetime.now; side_effects overrides if given."""
    m = patch('timing.datetime')
    return m


# ── timing._future ────────────────────────────────────────────────────────────

class TestFuture(unittest.TestCase):
    """Tests for the today-vs-tomorrow scheduling logic."""

    def _future(self, hour, minute, *, now=_NOW):
        with patch('timing.datetime') as mock_dt:
            mock_dt.now.return_value = now
            return timing._future(hour, minute)

    def test_future_time_is_today(self):
        result = self._future(14, 30)  # 2:30pm, now is 10:00am
        self.assertEqual(result.date(), _TODAY)
        self.assertEqual(result.hour, 14)
        self.assertEqual(result.minute, 30)

    def test_past_time_rolls_to_tomorrow(self):
        result = self._future(8, 0)  # 8:00am, now is 10:00am — already passed
        self.assertEqual(result.date(), _TOMORROW)
        self.assertEqual(result.hour, 8)
        self.assertEqual(result.minute, 0)

    def test_exact_current_minute_rolls_to_tomorrow(self):
        # _future uses <= so exact match also goes to tomorrow
        result = self._future(10, 0)  # same as _NOW
        self.assertEqual(result.date(), _TOMORROW)

    def test_one_minute_from_now_is_today(self):
        result = self._future(10, 1)
        self.assertEqual(result.date(), _TODAY)

    def test_seconds_zeroed(self):
        now = _NOW.replace(second=45)
        result = self._future(14, 0, now=now)
        self.assertEqual(result.second, 0)
        self.assertEqual(result.microsecond, 0)


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


if __name__ == '__main__':
    unittest.main()
