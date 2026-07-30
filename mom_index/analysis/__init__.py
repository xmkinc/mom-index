"""Pure deterministic classification and scoring."""

from .classifier import AnalysisResult, analyze_all, analyze_post, analyze_sector
from .scoring import compute_sector_index, interpret_index

__all__ = [
    "AnalysisResult",
    "analyze_all",
    "analyze_post",
    "analyze_sector",
    "compute_sector_index",
    "interpret_index",
]
