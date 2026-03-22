import pytest
from datetime import datetime, timedelta, timezone

# Tests written first — will fail until implementation exists
from app.services.status import format_envelope_message, _format_elapsed


class TestFormatElapsed:
    def test_zero_returns_empty(self):
        assert _format_elapsed(timedelta(seconds=0)) == ""

    def test_negative_returns_empty(self):
        assert _format_elapsed(timedelta(seconds=-5)) == ""

    def test_seconds(self):
        assert _format_elapsed(timedelta(seconds=30)) == "30s"

    def test_59_seconds(self):
        assert _format_elapsed(timedelta(seconds=59)) == "59s"

    def test_60_seconds_becomes_minutes(self):
        assert _format_elapsed(timedelta(seconds=60)) == "1m"

    def test_minutes(self):
        assert _format_elapsed(timedelta(seconds=180)) == "3m"

    def test_59_minutes(self):
        assert _format_elapsed(timedelta(seconds=3599)) == "59m"

    def test_60_minutes_becomes_hours(self):
        assert _format_elapsed(timedelta(seconds=3600)) == "1h"

    def test_hours(self):
        assert _format_elapsed(timedelta(seconds=7200)) == "2h"

    def test_23_hours(self):
        assert _format_elapsed(timedelta(seconds=86399)) == "23h"

    def test_24_hours_becomes_days(self):
        assert _format_elapsed(timedelta(seconds=86400)) == "1d"

    def test_days(self):
        assert _format_elapsed(timedelta(days=3)) == "3d"


class TestFormatEnvelopeMessage:
    def test_group_with_elapsed(self):
        ts = datetime(2026, 3, 22, 10, 30, tzinfo=timezone.utc)
        prev_ts = datetime(2026, 3, 22, 10, 27, tzinfo=timezone.utc)
        result = format_envelope_message(
            message="Hello",
            channel="agent-preview",
            from_name="Alice",
            chat_type="group",
            timestamp=ts,
            previous_timestamp=prev_ts,
        )
        assert result == "[agent-preview Alice +3m Sun 2026-03-22 10:30] Alice: Hello"

    def test_group_no_previous_timestamp(self):
        ts = datetime(2026, 3, 22, 10, 30, tzinfo=timezone.utc)
        result = format_envelope_message(
            message="Hello",
            channel="agent-preview",
            from_name="Alice",
            chat_type="group",
            timestamp=ts,
        )
        assert result == "[agent-preview Alice Sun 2026-03-22 10:30] Alice: Hello"

    def test_direct_mode_no_sender_prefix(self):
        ts = datetime(2026, 3, 22, 10, 30, tzinfo=timezone.utc)
        result = format_envelope_message(
            message="Hello",
            channel="agent-preview",
            from_name="Alice",
            chat_type="direct",
            timestamp=ts,
        )
        assert result == "[agent-preview Alice Sun 2026-03-22 10:30] Hello"

    def test_empty_from_name(self):
        ts = datetime(2026, 3, 22, 10, 30, tzinfo=timezone.utc)
        result = format_envelope_message(
            message="Hello",
            channel="agent-preview",
            from_name="",
            chat_type="group",
            timestamp=ts,
        )
        assert result == "[agent-preview Sun 2026-03-22 10:30] Hello"

    def test_elapsed_with_no_from_name(self):
        ts = datetime(2026, 3, 22, 10, 30, tzinfo=timezone.utc)
        prev_ts = datetime(2026, 3, 22, 10, 27, tzinfo=timezone.utc)
        result = format_envelope_message(
            message="Hello",
            channel="agent-preview",
            from_name="",
            chat_type="group",
            timestamp=ts,
            previous_timestamp=prev_ts,
        )
        assert result == "[agent-preview +3m Sun 2026-03-22 10:30] Hello"
