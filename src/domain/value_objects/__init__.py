"""
Domain value objects package.

This package contains the value objects that represent immutable
domain values in the Order Generation Service.
"""

from .drift_bounds import DriftBounds
from .target_percentage import TargetPercentage

__all__ = ["DriftBounds", "TargetPercentage"]
