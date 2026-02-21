import time
import re
import numpy as np
from typing import List, Optional, Dict
from modules.base import BaseModule, ModuleResult
from core.config import settings
import structlog

logger = structlog.get_logger()

FEATURE_KEYS = [
    "avg_sentence_len",
    "vocab_richness",
    "punctuation_density",
    "passive_voice_ratio",
    "avg_word_length",
    "connective_frequency",
    "question_frequency",
    "exclamation_frequency",
    "avg_paragraph_len",
    "capitalization_ratio",
    "digit_ratio",
    "short_sentence_ratio",
    "long_sentence_ratio",
    "unique_word_ratio",
]

CONNECTIVES = [
    "however", "therefore", "furthermore", "moreover", "although",
    "nevertheless", "consequently", "additionally", "meanwhile",
    "nonetheless", "otherwise", "subsequently", "thus", "hence",
]

PASSIVE_INDICATORS = ["was", "were", "been", "being", "is", "are", "am"]


def extract_features(text: str) -> np.ndarray:
    """Extract stylometric features from text."""
    if not text or len(text.strip()) < 50:
        return np.zeros(len(FEATURE_KEYS))

    sentences = [s.strip() for s in re.split(r"[.!?]+", text) if s.strip()]
    words = re.findall(r"\b[a-zA-Z]+\b", text.lower())
    paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]

    if not words:
        return np.zeros(len(FEATURE_KEYS))

    sentence_lens = [len(s.split()) for s in sentences] if sentences else [0]
    avg_sentence_len = np.mean(sentence_lens) if sentence_lens else 0.0

    vocab_richness = len(set(words)) / max(len(words), 1)

    punct_count = sum(1 for c in text if c in ".,;:!?-—()[]\"'")
    punctuation_density = punct_count / max(len(text), 1) * 100

    # Passive voice heuristic
    passive_count = sum(
        1 for s in sentences
        if any(ind in s.lower().split() for ind in PASSIVE_INDICATORS)
        and any(w.endswith("ed") or w.endswith("en") for w in s.split())
    )
    passive_voice_ratio = passive_count / max(len(sentences), 1)

    avg_word_length = np.mean([len(w) for w in words]) if words else 0.0

    connective_count = sum(1 for w in words if w in CONNECTIVES)
    connective_frequency = connective_count / max(len(words), 1) * 100

    question_frequency = text.count("?") / max(len(sentences), 1)
    exclamation_frequency = text.count("!") / max(len(sentences), 1)

    para_lens = [len(p.split()) for p in paragraphs] if paragraphs else [0]
    avg_paragraph_len = np.mean(para_lens)

    cap_words = [w for w in text.split() if w and w[0].isupper()]
    capitalization_ratio = len(cap_words) / max(len(text.split()), 1)

    digit_ratio = sum(1 for c in text if c.isdigit()) / max(len(text), 1)

    short_sentences = sum(1 for l in sentence_lens if l <= 8)
    long_sentences = sum(1 for l in sentence_lens if l >= 30)
    short_sentence_ratio = short_sentences / max(len(sentences), 1)
    long_sentence_ratio = long_sentences / max(len(sentences), 1)

    unique_word_ratio = len(set(words)) / max(len(words), 1)

    features = np.array([
        avg_sentence_len,
        vocab_richness,
        punctuation_density,
        passive_voice_ratio,
        avg_word_length,
        connective_frequency,
        question_frequency,
        exclamation_frequency,
        avg_paragraph_len,
        capitalization_ratio,
        digit_ratio,
        short_sentence_ratio,
        long_sentence_ratio,
        unique_word_ratio,
    ])

    return features


def deviation_score(profile_vec: np.ndarray, current_vec: np.ndarray) -> float:
    """Compute stylistic deviation between profile and current text."""
    from sklearn.metrics.pairwise import cosine_similarity

    # Normalize
    pnorm = np.linalg.norm(profile_vec)
    cnorm = np.linalg.norm(current_vec)

    if pnorm == 0 or cnorm == 0:
        return 0.5

    sim = cosine_similarity([profile_vec], [current_vec])[0][0]
    return float(1.0 - sim)  # 0=identical style, 1=completely different


def dp_privatize(vector: np.ndarray, epsilon: float = None) -> np.ndarray:
    """Add Laplace noise for differential privacy before storing."""
    eps = epsilon or settings.DP_EPSILON
    sensitivity = 1.0
    scale = sensitivity / eps
    noise = np.random.laplace(0, scale, size=vector.shape)
    return vector + noise


# In-memory profile store (fast cache; also persisted to DB via save_profile/load_profile)
_PROFILE_STORE: Dict[str, np.ndarray] = {}


async def load_profile(user_id: str, db=None) -> np.ndarray | None:
    """Load writing profile from DB into memory cache."""
    if user_id in _PROFILE_STORE:
        return _PROFILE_STORE[user_id]
    if db is None:
        return None
    try:
        from sqlalchemy import select
        from db.models import WritingProfile
        result = await db.execute(select(WritingProfile).where(WritingProfile.user_id == user_id))
        wp = result.scalar_one_or_none()
        if wp and wp.feature_vector:
            vec = np.array(wp.feature_vector)
            _PROFILE_STORE[user_id] = vec
            return vec
    except Exception:
        pass
    return None


async def save_profile(user_id: str, vector: np.ndarray, db=None):
    """Persist writing profile to DB."""
    _PROFILE_STORE[user_id] = vector
    if db is None:
        return
    try:
        from sqlalchemy import select
        from db.models import WritingProfile
        from datetime import datetime
        import uuid
        result = await db.execute(select(WritingProfile).where(WritingProfile.user_id == user_id))
        wp = result.scalar_one_or_none()
        if wp:
            wp.feature_vector = vector.tolist()
            wp.sample_count = (wp.sample_count or 0) + 1
            wp.last_updated = datetime.utcnow()
        else:
            db.add(WritingProfile(
                id=str(uuid.uuid4()), user_id=user_id,
                feature_vector=vector.tolist(), sample_count=1,
            ))
        await db.commit()
    except Exception:
        pass


class WritingProfileModule(BaseModule):
    module_id = "writing_profile"
    version = "1.0.0"
    default_weight = 0.25

    async def analyze(self, text: str, metadata: dict) -> ModuleResult:
        t0 = time.monotonic_ns()

        try:
            user_id = metadata.get("user_id")
            current_features = extract_features(text)

            feature_dict = {
                key: round(float(current_features[i]), 6)
                for i, key in enumerate(FEATURE_KEYS)
            }

            # No profile yet — store baseline and return neutral score
            if not user_id or user_id not in _PROFILE_STORE:
                if user_id:
                    # Store with DP noise
                    _PROFILE_STORE[user_id] = dp_privatize(current_features)
                    logger.info("writing_profile.baseline_created", user_id=user_id)

                return ModuleResult(
                    module_id=self.module_id,
                    score=0.0,
                    confidence=0.0,
                    evidence={
                        "status": "baseline_created" if user_id else "no_user_id",
                        "features": feature_dict,
                        "note": "First submission used as writing baseline.",
                    },
                    processing_ms=self._elapsed_ms(t0),
                )

            # Compare against stored profile
            stored_profile = _PROFILE_STORE[user_id]
            dev_score = deviation_score(stored_profile, current_features)

            # Compute per-feature deviations for evidence
            feature_deviations = {}
            for i, key in enumerate(FEATURE_KEYS):
                baseline_val = stored_profile[i]
                current_val = current_features[i]
                if abs(baseline_val) > 0.001:
                    pct_change = abs(current_val - baseline_val) / abs(baseline_val)
                    feature_deviations[key] = {
                        "baseline": round(float(baseline_val), 4),
                        "current": round(float(current_val), 4),
                        "deviation_pct": round(float(pct_change * 100), 2),
                    }

            # Update profile with exponential moving average
            _PROFILE_STORE[user_id] = dp_privatize(
                0.8 * stored_profile + 0.2 * current_features
            )

            # High-deviation features
            flagged_features = [
                k for k, v in feature_deviations.items()
                if v.get("deviation_pct", 0) > 50
            ]

            return ModuleResult(
                module_id=self.module_id,
                score=round(float(dev_score), 4),
                confidence=0.75,
                evidence={
                    "deviation_score": round(float(dev_score), 4),
                    "features": feature_dict,
                    "feature_deviations": feature_deviations,
                    "flagged_features": flagged_features,
                    "profile_samples": 1,  # Track in DB for real count
                },
                processing_ms=self._elapsed_ms(t0),
            )

        except Exception as e:
            logger.error("writing_profile.analyze_failed", error=str(e))
            return self._make_error_result(str(e), self._elapsed_ms(t0))
