"""Lightweight TF-IDF Cosine Similarity Duplicate & Known-Issue Radar.

Runs purely on NumPy + Python stdlib (zero scikit-learn dependency) against
historical escalated tickets in rideops_support_tickets.csv to surface:
  - Top matching historical eng_ticket_id records & similarity scores
  - Past Engineering outcome verdicts (Fixed vs Avoidable categories)
  - Pattern-level verdict breakdown so L1 knows immediately if similar
    escalations were duplicates, config issues, or missing info.
"""

from __future__ import annotations

import math
import re
from collections import Counter
from dataclasses import dataclass
from typing import Any

import numpy as np
import pandas as pd


STOPWORDS = {
    "a", "an", "the", "for", "to", "in", "on", "of", "at", "by", "is", "are",
    "was", "were", "be", "with", "from", "as", "it", "this", "that", "our",
    "we", "can", "get", "but", "still", "not", "via", "after", "even",
}

AVOIDABLE_OUTCOMES = {
    "Insufficient info - returned to L1",
    "Config issue - returned to L1",
    "Duplicate of known issue",
    "Not a bug - how-to",
    "Not reproducible",
}


def normalize_text(text: str) -> str:
    """Normalize ticket text so numeric variations (e.g., '33 employees', '6 AM')
    match their structural pattern cleanly."""
    s = str(text or "").lower().strip()
    # Normalize shift times like '6 am', '10 pm', '2 pm'
    s = re.sub(r"\b\d{1,2}\s*(?:am|pm)\b", " <shift_time> ", s)
    # Normalize durations like '25 mins', '20 mins', '15 days'
    s = re.sub(r"\b\d+\s*(?:mins?|minutes?|hrs?|hours?|days?|km)\b", " <metric> ", s)
    # Normalize standalone numbers (counts, route numbers)
    s = re.sub(r"\b\d+\b", " <num> ", s)
    s = re.sub(r"[^a-z0-9<>]+", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def tokenize(text: str, category: str = "") -> list[str]:
    """Extract informative unigrams, bigrams, and category tokens."""
    norm = normalize_text(text)
    raw_tokens = [t for t in norm.split() if len(t) > 1 and t not in STOPWORDS]
    bigrams = [f"{raw_tokens[i]}_{raw_tokens[i + 1]}" for i in range(len(raw_tokens) - 1)]
    cat_norm = normalize_text(category)
    cat_tokens = [f"cat_{t}" for t in cat_norm.split() if len(t) > 1 and t not in STOPWORDS]
    # Include unigrams + bigrams + mild category context
    return raw_tokens + bigrams + cat_tokens


@dataclass
class DuplicateRadarResult:
    matches: pd.DataFrame
    total_similar_count: int
    avoidable_share_pct: float
    fixed_share_pct: float
    duplicate_count: int
    top_outcome: str
    recommendation: str
    risk_level: str  # "high" | "medium" | "low"


class DuplicateRadarIndex:
    """Precomputed TF-IDF vector index over all historical escalated tickets."""

    def __init__(self, df: pd.DataFrame) -> None:
        esc = df[
            (df["escalated_to_eng"] == "Yes")
            & (df["eng_ticket_id"].notna())
            & (df["eng_ticket_id"].astype(str).str.strip() != "")
        ].copy()
        esc = esc.reset_index(drop=True)
        self.escalated_df = esc

        # Build vocabulary & IDF over combined description + category tokens
        doc_tokens: list[list[str]] = [
            tokenize(desc, cat)
            for desc, cat in zip(esc["description"].fillna(""), esc["category"].fillna(""))
        ]
        n_docs = len(doc_tokens)
        df_counts: Counter[str] = Counter()
        for toks in doc_tokens:
            for t in set(toks):
                df_counts[t] += 1

        self.vocab: dict[str, int] = {tok: idx for idx, tok in enumerate(sorted(df_counts.keys()))}
        self.idf: np.ndarray = np.array(
            [math.log((1 + n_docs) / (1 + df_counts[tok])) + 1.0 for tok in sorted(df_counts.keys())],
            dtype=np.float64,
        )

        # Build L2-normalized TF-IDF matrix (n_docs x n_vocab)
        mat = np.zeros((n_docs, len(self.vocab)), dtype=np.float64)
        for row_idx, toks in enumerate(doc_tokens):
            if not toks:
                continue
            tf = Counter(toks)
            for tok, cnt in tf.items():
                col_idx = self.vocab[tok]
                mat[row_idx, col_idx] = (1.0 + math.log(cnt)) * self.idf[col_idx]
            norm = np.linalg.norm(mat[row_idx])
            if norm > 0:
                mat[row_idx] /= norm
        self.matrix = mat
        self.desc_norms = esc["description"].fillna("").map(normalize_text).tolist()

    def _vectorize(self, description: str, category: str) -> np.ndarray:
        vec = np.zeros(len(self.vocab), dtype=np.float64)
        toks = tokenize(description, category)
        if not toks:
            return vec
        tf = Counter(toks)
        for tok, cnt in tf.items():
            col_idx = self.vocab.get(tok)
            if col_idx is not None:
                vec[col_idx] = (1.0 + math.log(cnt)) * self.idf[col_idx]
        norm = np.linalg.norm(vec)
        if norm > 0:
            vec /= norm
        return vec

    def search(
        self,
        description: str,
        category: str = "",
        exclude_ticket_id: str | None = None,
        top_k: int = 5,
        min_similarity: float = 0.20,
    ) -> DuplicateRadarResult:
        """Find top matching historical escalated tickets & synthesize verdict guidance."""
        if self.escalated_df.empty or not str(description or "").strip():
            empty = pd.DataFrame(
                columns=[
                    "eng_ticket_id",
                    "ticket_id",
                    "similarity_pct",
                    "category",
                    "description",
                    "eng_outcome",
                    "client_name",
                    "created_at",
                    "eng_handoffs",
                    "is_avoidable",
                ]
            )
            return DuplicateRadarResult(
                matches=empty,
                total_similar_count=0,
                avoidable_share_pct=0.0,
                fixed_share_pct=0.0,
                duplicate_count=0,
                top_outcome="No match",
                recommendation="Enter an issue description to scan historical Engineering tickets.",
                risk_level="low",
            )

        q_vec = self._vectorize(description, category)
        if float(np.linalg.norm(q_vec)) == 0.0:
            scores = np.zeros(len(self.escalated_df), dtype=np.float64)
        else:
            scores = self.matrix @ q_vec

        # Slight precision boost for exact normalized description match (capped at 1.0)
        q_norm = normalize_text(description)
        exact_mask = np.array([dn == q_norm for dn in self.desc_norms], dtype=bool)
        scores = np.where(exact_mask, np.minimum(1.0, scores * 0.65 + 0.35), scores)

        # Exclude the ticket itself when scanning an existing open ticket
        if exclude_ticket_id:
            self_mask = (self.escalated_df["ticket_id"].astype(str) == str(exclude_ticket_id)).to_numpy()
            scores = np.where(self_mask, -1.0, scores)

        # Gather all high-similarity matches (>= 0.55) for pattern statistics
        strong_indices = np.where(scores >= max(min_similarity, 0.50))[0]
        if len(strong_indices) == 0:
            strong_indices = np.where(scores >= min_similarity)[0]

        order = np.argsort(-scores)
        top_indices = [int(i) for i in order if scores[i] >= min_similarity][:top_k]

        if not top_indices:
            empty = pd.DataFrame(
                columns=[
                    "eng_ticket_id",
                    "ticket_id",
                    "similarity_pct",
                    "category",
                    "description",
                    "eng_outcome",
                    "client_name",
                    "created_at",
                    "eng_handoffs",
                    "is_avoidable",
                ]
            )
            return DuplicateRadarResult(
                matches=empty,
                total_similar_count=0,
                avoidable_share_pct=0.0,
                fixed_share_pct=0.0,
                duplicate_count=0,
                top_outcome="No close match",
                recommendation="No close historical Engineering match found. Follow L1 runbook checks before escalating.",
                risk_level="low",
            )

        # Build top-k display table
        rows: list[dict[str, Any]] = []
        for idx in top_indices:
            rec = self.escalated_df.iloc[idx]
            outcome = str(rec.get("eng_outcome", "") or "Pending")
            rows.append(
                {
                    "eng_ticket_id": rec["eng_ticket_id"],
                    "ticket_id": rec["ticket_id"],
                    "similarity_pct": round(float(scores[idx]) * 100.0, 1),
                    "category": rec["category"],
                    "description": rec["description"],
                    "eng_outcome": outcome,
                    "client_name": rec["client_name"],
                    "created_at": str(rec["created_at"])[:16],
                    "eng_handoffs": int(rec["eng_handoffs"]),
                    "is_avoidable": outcome in AVOIDABLE_OUTCOMES,
                }
            )
        matches_df = pd.DataFrame(rows)

        # Pattern statistics across all strong matches
        pattern_df = self.escalated_df.iloc[strong_indices]
        total_similar = len(pattern_df)
        outcomes = pattern_df["eng_outcome"].fillna("").astype(str)
        avoidable_n = int(outcomes.isin(AVOIDABLE_OUTCOMES).sum())
        fixed_n = int((outcomes == "Fixed").sum())
        dup_n = int((outcomes == "Duplicate of known issue").sum())
        avoidable_pct = round((avoidable_n / total_similar) * 100.0, 1) if total_similar else 0.0
        fixed_pct = round((fixed_n / total_similar) * 100.0, 1) if total_similar else 0.0
        top_outcome = str(outcomes.value_counts().index[0]) if total_similar else "Unknown"

        top_eng = matches_df.iloc[0]["eng_ticket_id"]
        top_sim = matches_df.iloc[0]["similarity_pct"]

        if dup_n >= 2 or (top_sim >= 85.0 and avoidable_pct >= 55.0):
            risk_level = "high"
            recommendation = (
                f"HIGH DEFLECTION OPPORTUNITY: {total_similar} similar escalations found "
                f"({avoidable_pct:.0f}% were avoidable; {dup_n} marked Duplicate of known issue). "
                f"Check {top_eng} or run the L1 config checklist before creating a new ENG ticket."
            )
        elif total_similar >= 3 and avoidable_pct >= 40.0:
            risk_level = "medium"
            recommendation = (
                f"RECURRING PATTERN: {total_similar} similar escalations found "
                f"({avoidable_pct:.0f}% avoidable, top verdict: {top_outcome}). "
                f"Link {top_eng} if identical, or complete all mandatory diagnostic checks first."
            )
        else:
            risk_level = "low"
            recommendation = (
                f"{total_similar} related historical escalation(s) found ({fixed_pct:.0f}% Fixed). "
                f"Reference {top_eng} in your handoff brief if preflight checks confirm a code defect."
            )

        return DuplicateRadarResult(
            matches=matches_df,
            total_similar_count=total_similar,
            avoidable_share_pct=avoidable_pct,
            fixed_share_pct=fixed_pct,
            duplicate_count=dup_n,
            top_outcome=top_outcome,
            recommendation=recommendation,
            risk_level=risk_level,
        )
