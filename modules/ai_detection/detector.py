import time
import random
from typing import List
from modules.base import BaseModule, ModuleResult
from core.config import settings
import structlog

logger = structlog.get_logger()


class AIDetectionModule(BaseModule):
    module_id = "ai_detection"
    version = "1.0.0"
    default_weight = 0.35

    def __init__(self):
        self.model = None
        self.tokenizer = None
        self.device = None
        self._mock = settings.AI_DETECTION_MOCK

        if not self._mock:
            self._load_model()

    def _load_model(self):
        try:
            import torch
            from transformers import RobertaTokenizer, RobertaForSequenceClassification

            self.device = torch.device("cuda" if (
                torch.cuda.is_available() and settings.AI_DETECTION_USE_GPU
            ) else "cpu")

            self.tokenizer = RobertaTokenizer.from_pretrained("roberta-base")
            self.model = RobertaForSequenceClassification.from_pretrained(
                settings.AI_DETECTION_MODEL_PATH
            ).eval()
            self.model.to(self.device)
            logger.info("ai_detection.model_loaded", device=str(self.device))
        except Exception as e:
            logger.warning("ai_detection.model_load_failed", error=str(e))
            self._mock = True

    async def warmup(self) -> None:
        if not self._mock:
            # Run a dummy inference to warm up CUDA / JIT
            await self.analyze("warmup text for model initialization", {})

    @property
    def is_healthy(self) -> bool:
        return self._mock or self.model is not None

    async def analyze(self, text: str, metadata: dict) -> ModuleResult:
        t0 = time.monotonic_ns()

        if self._mock:
            return self._mock_analyze(text, t0)

        return await self._real_analyze(text, metadata, t0)

    async def analyze(self, text: str, metadata: dict) -> ModuleResult:
        t0 = time.monotonic_ns()

        if self._mock:
            return self._mock_analyze(text, t0)

        try:
            import asyncio
            import torch

            chunks = self._chunk_text(text)
            chunk_scores = []

            for chunk in chunks:
                inputs = self.tokenizer(
                    chunk, return_tensors="pt",
                    truncation=True, max_length=512
                ).to(self.device)

                with torch.no_grad():
                    logits = self.model(**inputs).logits

                prob = torch.softmax(logits, dim=-1)[0][1].item()
                chunk_scores.append(prob)

            score = sum(chunk_scores) / len(chunk_scores) if chunk_scores else 0.0
            flagged = self._extract_flagged(text, chunk_scores)

            return ModuleResult(
                module_id=self.module_id,
                score=round(score, 4),
                confidence=0.85 if len(chunks) > 2 else 0.65,
                evidence={
                    "chunk_scores": [round(s, 4) for s in chunk_scores],
                    "flagged_segments": flagged,
                    "model_version": "roberta-ai-v2",
                    "chunks_analyzed": len(chunks),
                },
                processing_ms=self._elapsed_ms(t0),
            )
        except Exception as e:
            logger.error("ai_detection.analyze_failed", error=str(e))
            return self._make_error_result(str(e), self._elapsed_ms(t0))

    def _mock_analyze(self, text: str, t0: int) -> ModuleResult:
        """
        Deterministic mock based on text heuristics.
        Looks for patterns common in AI-generated text.
        """
        words = text.split()
        word_count = len(words)

        # Heuristic signals
        ai_phrases = [
            "it is worth noting", "in conclusion", "furthermore",
            "it is important to", "in summary", "additionally",
            "it is essential", "delve into", "nuanced", "multifaceted",
            "comprehensive", "leverage", "utilize", "paradigm",
        ]
        text_lower = text.lower()
        phrase_hits = sum(1 for p in ai_phrases if p in text_lower)
        phrase_score = min(phrase_hits / 5.0, 1.0)

        # Sentence length uniformity (AI tends to be more uniform)
        sentences = [s.strip() for s in text.split(".") if s.strip()]
        if sentences:
            lens = [len(s.split()) for s in sentences]
            avg_len = sum(lens) / len(lens)
            variance = sum((l - avg_len) ** 2 for l in lens) / len(lens)
            uniformity_score = max(0, 1.0 - (variance / 100.0))
        else:
            uniformity_score = 0.5

        score = (phrase_score * 0.6 + uniformity_score * 0.4)
        score = min(max(score, 0.0), 1.0)

        # Generate chunk-level scores
        chunk_size = max(1, word_count // 4)
        chunks = [words[i:i+chunk_size] for i in range(0, word_count, chunk_size)]
        chunk_scores = []
        for i, chunk in enumerate(chunks[:8]):
            variation = random.uniform(-0.1, 0.1)
            chunk_scores.append(round(min(max(score + variation, 0.0), 1.0), 4))

        flagged = self._extract_flagged(text, chunk_scores)

        return ModuleResult(
            module_id=self.module_id,
            score=round(score, 4),
            confidence=0.72,
            evidence={
                "chunk_scores": chunk_scores,
                "flagged_segments": flagged,
                "model_version": "mock-heuristic-v1",
                "phrase_hits": phrase_hits,
                "uniformity_score": round(uniformity_score, 4),
                "chunks_analyzed": len(chunks),
            },
            processing_ms=self._elapsed_ms(t0),
        )

    def _chunk_text(self, text: str, max_tokens: int = 512) -> List[str]:
        words = text.split()
        size = max_tokens - 10
        return [" ".join(words[i:i+size]) for i in range(0, len(words), size)]

    def _extract_flagged(self, text: str, chunk_scores: List[float]) -> List[str]:
        """Identify paragraphs/sections with high AI scores."""
        paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
        flagged = []
        threshold = 0.65

        for i, score in enumerate(chunk_scores):
            if score >= threshold and i < len(paragraphs):
                snippet = paragraphs[i][:120] + ("..." if len(paragraphs[i]) > 120 else "")
                flagged.append({"index": i, "score": score, "snippet": snippet})

        return flagged
