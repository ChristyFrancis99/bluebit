"""Unit tests for the core integrity system."""
import pytest
import asyncio
import sys
import os

# Add root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


# ── Aggregator Tests ──────────────────────────────────────────────────────────
class TestRiskAggregator:
    def setup_method(self):
        from core.aggregator import RiskAggregator
        self.agg = RiskAggregator()

    def _make_result(self, module_id, score, confidence=0.8):
        from modules.base import ModuleResult
        return ModuleResult(
            module_id=module_id,
            score=score,
            confidence=confidence,
            evidence={},
            processing_ms=100,
        )

    def test_low_risk(self):
        results = {
            "ai_detection": self._make_result("ai_detection", 0.1),
            "plagiarism": self._make_result("plagiarism", 0.05),
        }
        weights = {"ai_detection": 0.5, "plagiarism": 0.5}
        out = self.agg.aggregate(results, weights)
        assert out.risk_level == "LOW"
        assert out.integrity_score < 0.35

    def test_high_risk(self):
        results = {
            "ai_detection": self._make_result("ai_detection", 0.95),
            "plagiarism": self._make_result("plagiarism", 0.80),
        }
        weights = {"ai_detection": 0.5, "plagiarism": 0.5}
        out = self.agg.aggregate(results, weights)
        assert out.risk_level == "HIGH"
        assert out.integrity_score >= 0.65

    def test_medium_risk(self):
        results = {
            "ai_detection": self._make_result("ai_detection", 0.5),
            "plagiarism": self._make_result("plagiarism", 0.4),
        }
        weights = {"ai_detection": 0.5, "plagiarism": 0.5}
        out = self.agg.aggregate(results, weights)
        assert out.risk_level == "MEDIUM"

    def test_empty_results(self):
        out = self.agg.aggregate({}, {})
        assert out.integrity_score == 0.0
        assert out.risk_level == "LOW"

    def test_weighted_sum(self):
        results = {
            "a": self._make_result("a", 0.8),
            "b": self._make_result("b", 0.0),
        }
        weights = {"a": 0.8, "b": 0.2}
        out = self.agg.aggregate(results, weights)
        expected = (0.8 * 0.8 + 0.0 * 0.2) / 1.0
        assert abs(out.integrity_score - expected) < 0.01

    def test_zero_weight_excluded(self):
        results = {
            "ai_detection": self._make_result("ai_detection", 0.9),
            "proctoring": self._make_result("proctoring", 0.0),
        }
        weights = {"ai_detection": 1.0, "proctoring": 0.0}
        out = self.agg.aggregate(results, weights)
        # proctoring with weight=0 should not affect score
        assert abs(out.integrity_score - 0.9) < 0.01

    def test_flags_generated_for_high_scores(self):
        results = {
            "ai_detection": self._make_result("ai_detection", 0.95),
        }
        weights = {"ai_detection": 1.0}
        out = self.agg.aggregate(results, weights)
        assert len(out.flags) > 0
        assert out.flags[0]["severity"] == "HIGH"


# ── Writing Profile Tests ─────────────────────────────────────────────────────
class TestWritingProfile:
    def test_extract_features_returns_correct_shape(self):
        from modules.writing_profile.profiler import extract_features, FEATURE_KEYS
        text = "This is a test sentence. It has multiple sentences. Some are longer than others."
        features = extract_features(text)
        assert len(features) == len(FEATURE_KEYS)
        assert all(f >= 0 for f in features)

    def test_deviation_score_identical_texts(self):
        from modules.writing_profile.profiler import extract_features, deviation_score
        text = "Hello world. This is a test. " * 20
        f = extract_features(text)
        score = deviation_score(f, f)
        assert score < 0.01  # Identical vectors = zero deviation

    def test_deviation_score_different_texts(self):
        from modules.writing_profile.profiler import extract_features, deviation_score
        text1 = "Simple short sentences. Very basic. Easy words." * 10
        text2 = "The utilization of sophisticated multifaceted methodologies; furthermore, " \
                "these comprehensive paradigms necessitate nuanced consideration." * 10
        f1 = extract_features(text1)
        f2 = extract_features(text2)
        score = deviation_score(f1, f2)
        assert score > 0.1  # Different styles = non-zero deviation

    def test_dp_privatize_adds_noise(self):
        import numpy as np
        from modules.writing_profile.profiler import dp_privatize
        vec = np.ones(14)
        noisy = dp_privatize(vec, epsilon=1.0)
        assert not all(noisy == vec)


# ── AI Detection Mock Tests ───────────────────────────────────────────────────
class TestAIDetectionMock:
    @pytest.mark.asyncio
    async def test_analyze_returns_result(self):
        from modules.ai_detection.detector import AIDetectionModule
        module = AIDetectionModule()
        assert module._mock is True  # Should be in mock mode

        text = "This is a student's essay about climate change. " * 30
        result = await module.analyze(text, {})
        assert 0.0 <= result.score <= 1.0
        assert 0.0 <= result.confidence <= 1.0
        assert result.module_id == "ai_detection"
        assert result.processing_ms >= 0

    @pytest.mark.asyncio
    async def test_ai_phrases_increase_score(self):
        from modules.ai_detection.detector import AIDetectionModule
        module = AIDetectionModule()

        clean_text = "I went to school. My teacher was nice. We learned math." * 20
        ai_text = (
            "It is worth noting that furthermore, the multifaceted nuanced paradigm "
            "is essential to leverage. In conclusion, it is important to delve into "
            "the comprehensive utilization of this framework." * 15
        )

        clean_result = await module.analyze(clean_text, {})
        ai_result = await module.analyze(ai_text, {})
        assert ai_result.score > clean_result.score


# ── Plagiarism Tests ──────────────────────────────────────────────────────────
class TestPlagiarism:
    def test_fingerprint_similarity_identical(self):
        from modules.plagiarism.detector import DocumentFingerprinter
        fp = DocumentFingerprinter()
        text = "The quick brown fox jumps over the lazy dog. " * 20
        m1 = fp.fingerprint(text)
        m2 = fp.fingerprint(text)
        sim = fp.similarity(m1, m2)
        assert sim > 0.9

    def test_fingerprint_similarity_different(self):
        from modules.plagiarism.detector import DocumentFingerprinter
        fp = DocumentFingerprinter()
        t1 = "Physics quantum mechanics particle wave duality experiment."
        t2 = "Recipe baking flour sugar butter eggs chocolate cake oven."
        m1 = fp.fingerprint(t1)
        m2 = fp.fingerprint(t2)
        sim = fp.similarity(m1, m2)
        assert sim < 0.3

    def test_simhash_identical(self):
        from modules.plagiarism.detector import DocumentFingerprinter
        fp = DocumentFingerprinter()
        text = "The quick brown fox jumps over the lazy dog."
        h1 = fp.simhash_fingerprint(text)
        h2 = fp.simhash_fingerprint(text)
        assert fp.hamming_distance(h1, h2) == 0

    @pytest.mark.asyncio
    async def test_analyze_new_document(self):
        from modules.plagiarism.detector import PlagiarismModule, _DOCUMENT_INDEX
        _DOCUMENT_INDEX.clear()
        module = PlagiarismModule()
        text = "This is a completely unique test document. " * 30
        result = await module.analyze(text, {"submission_id": "test-123"})
        assert result.score >= 0.0
        assert result.module_id == "plagiarism"
