"""Tests for AI client retry logic and helper functions."""

import json
import time
from unittest.mock import MagicMock, patch, PropertyMock

import pytest


class TestStripMarkdownJson:
    """Tests for the strip_markdown_json helper."""

    def test_strip_json_with_fences(self):
        """Removes ```json ... ``` fences from JSON."""
        from emailtools.ai.client import strip_markdown_json

        raw = '```json\n{"key": "value"}\n```'
        assert strip_markdown_json(raw) == '{"key": "value"}'

    def test_strip_plain_fences(self):
        """Removes ``` ... ``` fences (without json label)."""
        from emailtools.ai.client import strip_markdown_json

        raw = '```\n{"key": "value"}\n```'
        assert strip_markdown_json(raw) == '{"key": "value"}'

    def test_passthrough_clean_json(self):
        """Clean JSON without fences passes through unchanged."""
        from emailtools.ai.client import strip_markdown_json

        raw = '{"key": "value"}'
        assert strip_markdown_json(raw) == '{"key": "value"}'

    def test_strips_whitespace(self):
        """Leading/trailing whitespace is stripped."""
        from emailtools.ai.client import strip_markdown_json

        raw = '  \n  {"key": "value"}  \n  '
        assert strip_markdown_json(raw) == '{"key": "value"}'

    def test_multiline_json(self):
        """Multi-line JSON inside fences is preserved."""
        from emailtools.ai.client import strip_markdown_json

        raw = '```json\n{\n  "key": "value",\n  "list": [1, 2]\n}\n```'
        result = strip_markdown_json(raw)
        parsed = json.loads(result)
        assert parsed == {"key": "value", "list": [1, 2]}


class TestAPIRetryLogic:
    """Tests for the retry-with-backoff logic in _call_api."""

    def _make_client(self):
        """Create an AIClient with mocked OpenAI client."""
        with patch("emailtools.ai.client.OpenAI"):
            with patch("emailtools.ai.client.settings") as mock_settings:
                mock_settings.openai_api_key = "test-key"
                mock_settings.openai_model = "gpt-4"
                mock_settings.openai_max_retries = 3
                mock_settings.openai_timeout = 30

                from emailtools.ai.client import AIClient
                client = AIClient()
                return client

    @staticmethod
    def _make_rate_limit_error():
        """Create a RateLimitError with properly linked httpx Request+Response."""
        from openai import RateLimitError
        from httpx import Response, Request

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

        client.client.chat.completions.create = MagicMock(
            side_effect=[rate_limit_exc, rate_limit_exc, mock_completion]
        )

        with patch("time.sleep"):  # skip delays
            result = client._call_api(
                messages=[{"role": "user", "content": "test"}],
                temperature=0.3,
                max_tokens=100,
            )

        assert result == '{"actions": []}'
        assert client.client.chat.completions.create.call_count == 3

    def test_retries_on_api_connection_error(self):
        """APIConnectionError triggers retry, eventually succeeds."""
        from openai import APIConnectionError
        from httpx import Request

        client = self._make_client()

        mock_request = Request(method="POST", url="https://api.openai.com/v1/chat/completions")
        conn_exc = APIConnectionError(request=mock_request)

        mock_completion = MagicMock()
        mock_completion.choices = [MagicMock()]
        mock_completion.choices[0].message.content = '{"result": "ok"}'

        client.client.chat.completions.create = MagicMock(
            side_effect=[conn_exc, mock_completion]
        )

        with patch("time.sleep"):
            result = client._call_api(
                messages=[{"role": "user", "content": "test"}],
                temperature=0.3,
                max_tokens=100,
            )

        assert result == '{"result": "ok"}'
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

        assert result == '{"status": "ok"}'
        assert client.client.chat.completions.create.call_count == 1
        assert len(sleep_calls) == 0


class TestGenerateReportInsightsEdgeCases:
    """Tests for generate_report_insights with empty/edge-case inputs."""

    def test_empty_input_returns_empty_structure(self):
        """Empty action_details and email_summaries returns default empty structure."""
        with patch("emailtools.ai.client.OpenAI"):
            with patch("emailtools.ai.client.settings") as mock_settings:
                mock_settings.openai_api_key = "test-key"
                mock_settings.openai_model = "gpt-4"
                mock_settings.openai_max_retries = 3
                mock_settings.openai_timeout = 30

                from emailtools.ai.client import AIClient
                client = AIClient()

        result = client.generate_report_insights(
            action_details="",
            email_summaries="",
        )

        assert "executive_summary" in result
        assert result["executive_summary"]["headline"] == "No recent activity to report"
        assert "risk_radar" in result
        assert "recommendations" in result
