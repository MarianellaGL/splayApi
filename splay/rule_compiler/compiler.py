"""
Rule Compiler - Compiles rules text to GameSpec using LLM.

The compiler:
1. Accepts rules text
2. Uses structured prompts to extract game structure
3. Validates the output
4. Returns a compiled GameSpec

IMPORTANT: The LLM is used at BUILD-TIME only.
It does NOT make gameplay decisions at runtime.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any
from enum import Enum

from ..spec_schema import GameSpec, validate_spec
from ..spec_schema.validation import ValidationResult
from .cache import SpecCache


class CompilationStatus(Enum):
    """Status of compilation."""
    SUCCESS = "success"
    PARTIAL = "partial"  # Some elements couldn't be extracted
    FAILED = "failed"
    CACHED = "cached"  # Retrieved from cache


@dataclass
class CompilationResult:
    """
    Result of compiling rules text.
    """
    status: CompilationStatus
    spec: GameSpec | None = None
    validation: ValidationResult | None = None

    # Extraction details
    extracted_cards: int = 0
    extracted_actions: int = 0
    extracted_effects: int = 0

    # Issues encountered
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

    # For human review
    uncertain_extractions: list[dict[str, Any]] = field(default_factory=list)

    # Generated tests
    generated_tests: list[str] = field(default_factory=list)

    # Metadata
    rules_hash: str = ""
    compilation_time_ms: int = 0


@dataclass
class RuleCompiler:
    """
    Compiles rules text into GameSpec.

    Usage:
        compiler = RuleCompiler()
        result = compiler.compile(rules_text)
        if result.status == CompilationStatus.SUCCESS:
            spec = result.spec
    """
    cache: SpecCache | None = None
    llm_client: Any = None  # STUB: LLM client interface

    def __init__(
        self,
        cache_dir: str | None = None,
        use_cache: bool = True,
    ):
        if use_cache:
            self.cache = SpecCache(cache_dir=cache_dir)
        else:
            self.cache = None

    def compile(
        self,
        rules_text: str,
        game_name: str | None = None,
        faq_text: str | None = None,
        force_recompile: bool = False,
    ) -> CompilationResult:
        """
        Compile rules text into a GameSpec.

        Args:
            rules_text: The game rules as plain text
            game_name: Optional game name (extracted if not provided)
            faq_text: Optional FAQ text for clarifications
            force_recompile: Skip cache lookup

        Returns:
            CompilationResult with status and spec
        """
        import time
        start_time = time.time()

        # Check cache first
        if self.cache and not force_recompile:
            cached_spec = self.cache.get(rules_text)
            if cached_spec:
                return CompilationResult(
                    status=CompilationStatus.CACHED,
                    spec=cached_spec,
                    rules_hash=self._hash_rules(rules_text),
                )

        # Compile using LLM
        try:
            spec, extraction_info = self._compile_with_llm(
                rules_text, game_name, faq_text
            )
        except Exception as e:
            return CompilationResult(
                status=CompilationStatus.FAILED,
                errors=[str(e)],
                rules_hash=self._hash_rules(rules_text),
            )

        # Validate the spec
        validation = validate_spec(spec)

        # Determine status
        if not validation.valid:
            status = CompilationStatus.FAILED
        elif validation.warnings:
            status = CompilationStatus.PARTIAL
        else:
            status = CompilationStatus.SUCCESS

        # Cache successful compilations
        if status in {CompilationStatus.SUCCESS, CompilationStatus.PARTIAL}:
            if self.cache:
                self.cache.put(rules_text, spec)

        compilation_time = int((time.time() - start_time) * 1000)

        return CompilationResult(
            status=status,
            spec=spec,
            validation=validation,
            extracted_cards=extraction_info.get("cards", 0),
            extracted_actions=extraction_info.get("actions", 0),
            extracted_effects=extraction_info.get("effects", 0),
            warnings=validation.warnings if validation else [],
            errors=validation.errors if validation else [],
            uncertain_extractions=extraction_info.get("uncertain", []),
            rules_hash=self._hash_rules(rules_text),
            compilation_time_ms=compilation_time,
        )

    def _compile_with_llm(
        self,
        rules_text: str,
        game_name: str | None,
        faq_text: str | None,
    ) -> tuple[GameSpec, dict[str, Any]]:
        """
        Use LLM to extract game structure from rules.

        STUB: This is where the LLM integration would go.
        For MVP, returns a minimal spec.
        """
        # STUB: LLM extraction
        # In real implementation:
        # 1. Send rules to LLM with extraction prompts
        # 2. Parse structured output
        # 3. Convert to GameSpec

        # For now, return a minimal spec
        spec = GameSpec(
            game_id=self._generate_id(game_name or "unknown"),
            game_name=game_name or "Unknown Game",
            version="1.0.0",
            min_players=2,
            max_players=4,
        )

        extraction_info = {
            "cards": 0,
            "actions": 0,
            "effects": 0,
            "uncertain": [
                {
                    "type": "stub",
                    "message": "LLM compilation not implemented - using minimal spec",
                }
            ],
        }

        return spec, extraction_info

    def _hash_rules(self, rules_text: str) -> str:
        """Hash rules text for caching."""
        import hashlib
        return hashlib.sha256(rules_text.encode()).hexdigest()[:16]

    def _generate_id(self, name: str) -> str:
        """Generate a game ID from name."""
        return name.lower().replace(" ", "_").replace("-", "_")


def compile_rules(
    rules_text: str,
    game_name: str | None = None,
    cache_dir: str | None = None,
) -> CompilationResult:
    """
    Convenience function to compile rules.
    """
    compiler = RuleCompiler(cache_dir=cache_dir)
    return compiler.compile(rules_text, game_name=game_name)
