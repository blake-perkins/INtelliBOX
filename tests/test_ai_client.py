"""Tests for AI client retry logic and helper functions."""

import json
from unittest.mock import MagicMock, patch

import pytest


class TestStripMarkdownJson:
    """Tests for the strip_markdown_json helper."""

    def test_strip_json_with_fences(self):
        """Removes ```json ... ``` fences from JSON."""
        from intellibox.ai.client import strip_markdown_json

        raw = '```json\n{"key": "value"}\n```'
        assert strip_markdown_json(raw) == '{"key": "value"}'

    def test_strip_plain_fences(self):
        """Removes ``` ... ``` fences (without json label)."""
        from intellibox.ai.client import strip_markdown_json

        raw = '```\n{"key": "value"}\n```'
        assert strip_markdown_json(raw) == '{"key": "value"}'

    def test_passthrough_clean_json(self):
        """Clean JSON without fences passes through unchanged."""
        from intellibox.ai.client import strip_markdown_json

        raw = '{"key": "value"}'
        assert strip_markdown_json(raw) == '{"key": "value"}'

    def test_strips_whitespace(self):
        """Leading/trailing whitespace is stripped."""
        from intellibox.ai.client import strip_markdown_json

        raw = '  \n  {"key": "value"}  \n  '
        assert strip_markdown_json(raw) == '{"key": "value"}'

    def test_multiline_json(self):
        """Multi-line JSON inside fences is preserved."""
        from intellibox.ai.client import strip_markdown_json

        raw = '```json\n{\n  "key": "value",\n  "list": [1, 2]\n}\n```'
        result = strip_markdown_json(raw)
        parsed = json.loads(result)
        assert parsed == {"key": "value", "list": [1, 2]}


class TestAPIRetryLogic:
    """Tests for the retry-with-backoff logic in _call_api."""

    def _make_client(self):
        """Create an AIClient with mocked OpenAI client."""
        with patch("intellibox.ai.client.OpenAI"):
            with patch("intellibox.ai.client.settings") as mock_settings:
                mock_settings.openai_api_key = "test-key"
                mock_settings.openai_model = "gpt-4"
                mock_settings.openai_max_retries = 3
                mock_settings.openai_timeout = 30

                from intellibox.ai.client import AIClient
                client = AIClient()
                return client

    @staticmethod
    def _make_rate_limit_error():
        """Create a RateLimitError with properly linked httpx Request+Response."""
        from httpx import Request, Response
        from openai import RateLimitError

        req = Request(method="POST", url="https://api.openai.com/v1/chat/completions")
        resp = Response(status_code=429, request=req)
        return RateLimitError(
            message="Rate limit exceeded",
            response=resp,
            body=None,
        )

    def test_retries_on_rate_limit(self):
        """RateLimitError triggers retry, eventually succeeds."""
        client = self._make_client()

        rate_limit_exc = self._make_rate_limit_error()

        mock_completion = MagicMock()
        mock_completion.choices = [MagicMock()]
        mock_completion.choices[0].message.content = '{"actions": []}'
        mock_completion.model = "gpt-4"
        mock_completion.usage = MagicMock(prompt_tokens=10, completion_tokens=5, total_tokens=15)

        client.client.chat.completions.create = MagicMock(
            side_effect=[rate_limit_exc, rate_limit_exc, mock_completion]
        )

        with patch("time.sleep"):  # skip delays
            result = client._call_api(
                messages=[{"role": "user", "content": "test"}],
                temperature=0.3,
                max_tokens=100,
            )

        assert result.content == '{"actions": []}'
        assert result.retry_count == 2
        assert client.client.chat.completions.create.call_count == 3

    def test_retries_on_api_connection_error(self):
        """APIConnectionError triggers retry, eventually succeeds."""
        from httpx import Request
        from openai import APIConnectionError

        client = self._make_client()

        mock_request = Request(method="POST", url="https://api.openai.com/v1/chat/completions")
        conn_exc = APIConnectionError(request=mock_request)

        mock_completion = MagicMock()
        mock_completion.choices = [MagicMock()]
        mock_completion.choices[0].message.content = '{"result": "ok"}'
        mock_completion.model = "gpt-4"
        mock_completion.usage = MagicMock(prompt_tokens=10, completion_tokens=5, total_tokens=15)

        client.client.chat.completions.create = MagicMock(
            side_effect=[conn_exc, mock_completion]
        )

        with patch("time.sleep"):
            result = client._call_api(
                messages=[{"role": "user", "content": "test"}],
                temperature=0.3,
                max_tokens=100,
            )

        assert result.content == '{"result": "ok"}'
        assert result.retry_count == 1
        assert client.client.chat.completions.create.call_count == 2

    def test_gives_up_after_max_retries(self):
        """After max_retries exhausted, the exception is re-raised."""
        from openai import RateLimitError

        client = self._make_client()

        rate_limit_exc = self._make_rate_limit_error()

        client.client.chat.completions.create = MagicMock(
            side_effect=rate_limit_exc
        )

        with patch("time.sleep"):
            with pytest.raises(RateLimitError):
                client._call_api(
                    messages=[{"role": "user", "content": "test"}],
                    temperature=0.3,
                    max_tokens=100,
                )

        # 1 initial + 3 retries = 4 total (max_retries=3)
        assert client.client.chat.completions.create.call_count == 4

    def test_exponential_backoff_timing(self):
        """Backoff delays follow exponential pattern: 1s, 2s, 4s."""
        from openai import RateLimitError

        client = self._make_client()

        rate_limit_exc = self._make_rate_limit_error()

        client.client.chat.completions.create = MagicMock(
            side_effect=rate_limit_exc
        )

        sleep_calls = []

        with patch("time.sleep", side_effect=lambda s: sleep_calls.append(s)):
            with pytest.raises(RateLimitError):
                client._call_api(
                    messages=[{"role": "user", "content": "test"}],
                    temperature=0.3,
                    max_tokens=100,
                )

        # 3 retries = 3 sleep calls
        assert len(sleep_calls) == 3
        assert sleep_calls[0] == 1   # 2^0
        assert sleep_calls[1] == 2   # 2^1
        assert sleep_calls[2] == 4   # 2^2

    def test_no_retry_on_non_retryable_error(self):
        """Non-retryable exceptions (e.g. ValueError) propagate immediately."""
        client = self._make_client()

        client.client.chat.completions.create = MagicMock(
            side_effect=ValueError("bad input")
        )

        with pytest.raises(ValueError, match="bad input"):
            client._call_api(
                messages=[{"role": "user", "content": "test"}],
                temperature=0.3,
                max_tokens=100,
            )

        # Only 1 call, no retries
        assert client.client.chat.completions.create.call_count == 1

    def test_success_on_first_try(self):
        """Successful first attempt doesn't trigger any retries."""
        client = self._make_client()

        mock_completion = MagicMock()
        mock_completion.choices = [MagicMock()]
        mock_completion.choices[0].message.content = '{"status": "ok"}'
        mock_completion.model = "gpt-4"
        mock_completion.usage = MagicMock(prompt_tokens=20, completion_tokens=10, total_tokens=30)

        client.client.chat.completions.create = MagicMock(
            return_value=mock_completion
        )

        sleep_calls = []
        with patch("time.sleep", side_effect=lambda s: sleep_calls.append(s)):
            result = client._call_api(
                messages=[{"role": "user", "content": "test"}],
                temperature=0.3,
                max_tokens=100,
            )

        assert result.content == '{"status": "ok"}'
        assert result.prompt_tokens == 20
        assert result.completion_tokens == 10
        assert result.total_tokens == 30
        assert result.retry_count == 0
        assert client.client.chat.completions.create.call_count == 1
        assert len(sleep_calls) == 0


class TestRetryTimingAccuracy:
    """Tests that verify the actual time.sleep values passed during retries."""

    def _make_client(self, max_retries=3):
        with patch("intellibox.ai.client.OpenAI"):
            with patch("intellibox.ai.client.settings") as mock_settings:
                mock_settings.openai_api_key = "test-key"
                mock_settings.openai_model = "gpt-4"
                mock_settings.openai_max_retries = max_retries
                mock_settings.openai_timeout = 30
                from intellibox.ai.client import AIClient
                return AIClient()

    @staticmethod
    def _make_rate_limit_error():
        from httpx import Request, Response
        from openai import RateLimitError
        req = Request(method="POST", url="https://api.openai.com/v1/chat/completions")
        resp = Response(status_code=429, request=req)
        return RateLimitError(message="Rate limit", response=resp, body=None)

    def test_backoff_exact_values_5_retries(self):
        """With max_retries=5, verify backoff is 1, 2, 4, 8, 16 seconds."""
        client = self._make_client(max_retries=5)
        exc = self._make_rate_limit_error()
        client.client.chat.completions.create = MagicMock(side_effect=exc)

        sleep_calls = []
        with patch("time.sleep", side_effect=lambda s: sleep_calls.append(s)):
            with pytest.raises(Exception):
                client._call_api(
                    messages=[{"role": "user", "content": "test"}],
                    temperature=0.3, max_tokens=100,
                )

        assert sleep_calls == [1, 2, 4, 8, 16]

    def test_total_retry_time_is_bounded(self):
        """Total backoff time for max_retries=3 should be exactly 7 seconds (1+2+4)."""
        client = self._make_client(max_retries=3)
        exc = self._make_rate_limit_error()
        client.client.chat.completions.create = MagicMock(side_effect=exc)

        sleep_calls = []
        with patch("time.sleep", side_effect=lambda s: sleep_calls.append(s)):
            with pytest.raises(Exception):
                client._call_api(
                    messages=[{"role": "user", "content": "test"}],
                    temperature=0.3, max_tokens=100,
                )

        assert sum(sleep_calls) == 7  # 1 + 2 + 4

    def test_mixed_error_types_all_retry(self):
        """Different retryable errors in sequence all trigger retries."""
        from httpx import Request, Response
        from openai import APIConnectionError, APIStatusError

        client = self._make_client(max_retries=3)

        req = Request(method="POST", url="https://api.openai.com/v1/chat/completions")
        resp = Response(status_code=500, request=req)

        rate_err = self._make_rate_limit_error()
        conn_err = APIConnectionError(request=req)
        api_err = APIStatusError(message="Server error", response=resp, body=None)

        mock_completion = MagicMock()
        mock_completion.choices = [MagicMock()]
        mock_completion.choices[0].message.content = '{"ok": true}'
        mock_completion.model = "gpt-4"
        mock_completion.usage = MagicMock(prompt_tokens=10, completion_tokens=5, total_tokens=15)

        client.client.chat.completions.create = MagicMock(
            side_effect=[rate_err, conn_err, api_err, mock_completion]
        )

        sleep_calls = []
        with patch("time.sleep", side_effect=lambda s: sleep_calls.append(s)):
            result = client._call_api(
                messages=[{"role": "user", "content": "test"}],
                temperature=0.3, max_tokens=100,
            )

        assert result.content == '{"ok": true}'
        assert result.retry_count == 3
        assert client.client.chat.completions.create.call_count == 4
        assert len(sleep_calls) == 3  # 3 retries before success

    def test_zero_retries_fails_immediately(self):
        """With max_retries=0, no retries occur."""
        client = self._make_client(max_retries=0)
        exc = self._make_rate_limit_error()
        client.client.chat.completions.create = MagicMock(side_effect=exc)

        sleep_calls = []
        with patch("time.sleep", side_effect=lambda s: sleep_calls.append(s)):
            with pytest.raises(Exception):
                client._call_api(
                    messages=[{"role": "user", "content": "test"}],
                    temperature=0.3, max_tokens=100,
                )

        assert client.client.chat.completions.create.call_count == 1
        assert len(sleep_calls) == 0


class TestGenerateReportInsightsEdgeCases:
    """Tests for generate_report_insights with empty/edge-case inputs."""

    def test_empty_input_returns_empty_structure(self):
        """Empty action_details and email_summaries returns default empty structure."""
        with patch("intellibox.ai.client.OpenAI"):
            with patch("intellibox.ai.client.settings") as mock_settings:
                mock_settings.openai_api_key = "test-key"
                mock_settings.openai_model = "gpt-4"
                mock_settings.openai_max_retries = 3
                mock_settings.openai_timeout = 30

                from intellibox.ai.client import AIClient
                client = AIClient()

        result = client.generate_report_insights(
            action_details="",
            email_summaries="",
        )

        assert "executive_summary" in result
        assert result["executive_summary"]["headline"] == "No recent activity to report"
        assert "risk_radar" in result
        assert "recommendations" in result
