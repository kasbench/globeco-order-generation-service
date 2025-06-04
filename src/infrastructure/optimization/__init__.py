"""
Optimization infrastructure module for portfolio rebalancing.

This module provides concrete implementations of optimization engines including:
- CVXPY-based mathematical optimization solver
- Portfolio constraint formulation and validation
- Mathematical precision handling for financial calculations
"""

from src.infrastructure.optimization.cvxpy_solver import CVXPYOptimizationEngine

__all__ = [
    "CVXPYOptimizationEngine",
]
