import time
import re
import hashlib
from typing import List, Dict
from modules.base import BaseModule, ModuleResult
import structlog

logger = structlog.get_logger()

# In-memory document store for demo (replace with Redis/DB in prod)
_DOCUMENT_INDEX: Dict[str, dict] = {}


class DocumentFingerprinter:
    def __init__(self, num_perm: int = 128):
        self.num_perm = num_perm

    def fingerprint(self, text: str) -> "MinHash":
        try:
            from datasketch import MinHash
            m = MinHash(num_perm=self.num_perm)
            for shingle in self._shingle(text):
                m.update(shingle.encode("utf8"))
            return m
        except ImportError:
            return None

    def _shingle(self, text: str, k: int = 5):
        tokens = re.findall(r"\w+", text.lower())
        return {" ".join(tokens[i:i+k]) for i in range(len(tokens) - k + 1)}

    def similarity(self, m1, m2) -> float:
        if m1 is None or m2 is None:
            return 0.0
        return m1.jaccard(m2)

    def simhash_fingerprint(self, text: str) -> int:
        """Fast 64-bit SimHash for near-duplicate detection."""
        tokens = re.findall(r"\w+", text.lower())
        v = [0] * 64
        for token in tokens:
            h = int(hashlib.md5(token.encode()).hexdigest(), 16)
            for i in range(64):
                if h & (1 << i):
                    v[i] += 1
                else:
                    v[i] -= 1
        fingerprint = 0
        for i in range(64):
            if v[i] > 0:
                fingerprint |= (1 << i)
        return fingerprint

    def hamming_distance(self, h1: int, h2: int) -> int:
        x = h1 ^ h2
        return bin(x).count("1")


class PlagiarismModule(BaseModule):
    module_id = "plagiarism"
    version = "1.0.0"
    default_weight = 0.40

    # Known suspicious phrases / common essay mill content
    KNOWN_SUSPICIOUS = [
        "this essay will examine",
        "throughout this paper",
        "as stated by many scholars",
        "according to various sources",
    ]

    def __init__(self):
        self.fingerprinter = DocumentFingerprinter(num_perm=128)
        self._lsh = None
        self._init_lsh()

    def _init_lsh(self):
        try:
            from datasketch import MinHashLSH
            self._lsh = MinHashLSH(threshold=0.5, num_perm=128)
            logger.info("plagiarism.lsh_initialized")
        except ImportError:
            logger.warning("plagiarism.datasketch_not_available")

    @property
    def is_healthy(self) -> bool:
        return True  # Works with or without datasketch

    async def analyze(self, text: str, metadata: dict) -> ModuleResult:
        t0 = time.monotonic_ns()

        try:
            submission_id = metadata.get("submission_id", "unknown")
            user_id = metadata.get("user_id", "unknown")

            matches = []
            max_similarity = 0.0

            # 1. Check against known stored documents
            text_fp = self.fingerprinter.fingerprint(text)
            text_sh = self.fingerprinter.simhash_fingerprint(text)

            for doc_id, stored in _DOCUMENT_INDEX.items():
                if doc_id == submission_id:
                    continue

                # SimHash quick filter
                hamming = self.fingerprinter.hamming_distance(
                    text_sh, stored.get("simhash", 0)
                )
                if hamming > 20:  # Too different, skip expensive MinHash
                    continue

                # MinHash similarity
                similarity = self.fingerprinter.similarity(
                    text_fp, stored.get("minhash")
                )
                if similarity > 0.3:
                    matches.append({
                        "doc_id": doc_id,
                        "similarity": round(similarity, 4),
                        "user_id": stored.get("user_id", "unknown"),
                    })
                    max_similarity = max(max_similarity, similarity)

            # 2. Check for suspicious known phrases
            text_lower = text.lower()
            suspicious_hits = [
                phrase for phrase in self.KNOWN_SUSPICIOUS
                if phrase in text_lower
            ]

            # 3. Internal repetition analysis (self-plagiarism signal)
            paragraphs = [p.strip() for p in text.split("\n\n") if len(p.strip()) > 50]
            internal_similarity = self._check_internal_repetition(paragraphs)

            # Store this document for future comparisons
            if text_fp is not None:
                _DOCUMENT_INDEX[submission_id] = {
                    "minhash": text_fp,
                    "simhash": text_sh,
                    "user_id": user_id,
                }

            # Compute final score
            match_score = max_similarity if matches else 0.0
            phrase_score = min(len(suspicious_hits) / 3.0, 1.0)
            score = (match_score * 0.7) + (phrase_score * 0.2) + (internal_similarity * 0.1)
            score = min(max(score, 0.0), 1.0)

            return ModuleResult(
                module_id=self.module_id,
                score=round(score, 4),
                confidence=0.80 if matches else 0.60,
                evidence={
                    "matches": matches[:10],  # top 10
                    "max_similarity": round(max_similarity, 4),
                    "suspicious_phrases": suspicious_hits,
                    "internal_repetition": round(internal_similarity, 4),
                    "documents_checked": len(_DOCUMENT_INDEX),
                },
                processing_ms=self._elapsed_ms(t0),
            )

        except Exception as e:
            logger.error("plagiarism.analyze_failed", error=str(e))
            return self._make_error_result(str(e), self._elapsed_ms(t0))

    def _check_internal_repetition(self, paragraphs: List[str]) -> float:
        """Detect if paragraphs repeat content (copy-paste within doc)."""
        if len(paragraphs) < 2:
            return 0.0

        fps = [self.fingerprinter.fingerprint(p) for p in paragraphs]
        max_sim = 0.0
        for i in range(len(fps)):
            for j in range(i + 1, len(fps)):
                sim = self.fingerprinter.similarity(fps[i], fps[j])
                max_sim = max(max_sim, sim)
        return max_sim
