"""Security tests — verify secrets are handled safely."""

import os
from unittest.mock import patch

import pytest

from lib.config import _require_env, get_supabase_secret_key


class TestRequireEnvRaisesOnMissing:
    def test_raises_runtime_error(self, monkeypatch):
        monkeypatch.delenv("NONEXISTENT_VAR_12345", raising=False)
        with pytest.raises(RuntimeError, match="Missing required environment variable"):
            _require_env("NONEXISTENT_VAR_12345")


class TestSupabaseSecretKeyNotLeakedInError:
    def test_error_message_has_no_secret_values(self, monkeypatch):
        monkeypatch.delenv("SUPABASE_SECRET_KEY", raising=False)
        monkeypatch.delenv("K_SERVICE", raising=False)

        with pytest.raises(RuntimeError) as exc_info:
            get_supabase_secret_key()

        error_msg = str(exc_info.value)
        # The error should contain helpful instructions, not secret values
        assert "SUPABASE_SECRET_KEY" in error_msg  # mentions the var name
        assert "secret-key" not in error_msg.lower().replace("supabase_secret_key", "")
        assert len(error_msg) < 300  # not dumping large data
