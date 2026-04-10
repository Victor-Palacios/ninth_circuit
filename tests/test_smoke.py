"""Smoke tests — verify modules load and constants are sane."""


class TestAllPipelineModulesImport:
    def test_imports_succeed(self):
        import pipeline.fetch
        import pipeline.classify_shared
        import pipeline.classify_free
        import pipeline.extract
        import pipeline.backup
        import pipeline.qa_check
        import pipeline.backfill
        import lib.config
        import lib.supabase_client
        import lib.gemini_client


class TestClassificationPromptIsValid:
    def test_prompt_contains_key_terms(self):
        from pipeline.classify_shared import CLASSIFICATION_PROMPT

        assert len(CLASSIFICATION_PROMPT) > 100
        assert "asylum" in CLASSIFICATION_PROMPT.lower()
        assert "JSON" in CLASSIFICATION_PROMPT
        assert "answer" in CLASSIFICATION_PROMPT
        assert "yes" in CLASSIFICATION_PROMPT
        assert "no" in CLASSIFICATION_PROMPT
