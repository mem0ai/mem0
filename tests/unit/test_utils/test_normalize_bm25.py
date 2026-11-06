"""Tests for mem0.utils.scoring.normalize_bm25."""

import math

from mem0.utils.scoring import normalize_bm25


class TestNormalizeBm25:
    def test_midpoint_returns_half(self):
        """At the midpoint, sigmoid should return ~0.5."""
        result = normalize_bm25(5.0, 5.0, 0.7)
        assert abs(result - 0.5) < 1e-10

    def test_above_midpoint(self):
        result = normalize_bm25(10.0, 5.0, 0.7)
        assert 0.5 < result < 1.0

    def test_below_midpoint(self):
        result = normalize_bm25(2.0, 5.0, 0.7)
        assert 0.0 < result < 0.5

    def test_very_negative_score_no_crash(self):
        """Very negative raw_score should not crash with OverflowError."""
        result = normalize_bm25(-1000.0, 5.0, 0.7)
        assert result == 0.0

    def test_very_large_score(self):
        """Very large raw_score should approach 1.0."""
        result = normalize_bm25(1000.0, 5.0, 0.7)
        assert result == 1.0

    def test_zero_score(self):
        result = normalize_bm25(0.0, 5.0, 0.7)
        assert 0.0 < result < 0.5
