"""
Rule Compiler - Compiles rules text into GameSpec.

The rule compiler:
1. Takes rules text (plain text, PDF, etc.)
2. Uses LLM at BUILD-TIME to extract game structure
3. Produces a validated GameSpec
4. Caches results by content hash

The LLM is NEVER used at runtime for gameplay decisions.
"""

from .compiler import RuleCompiler, CompilationResult
from .cache import SpecCache, CacheEntry
from .prompts import CompilerPrompts

__all__ = [
    "RuleCompiler",
    "CompilationResult",
    "SpecCache",
    "CacheEntry",
    "CompilerPrompts",
]
