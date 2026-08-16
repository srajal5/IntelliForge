"""Shared enumerations for the AI Intelligence Pipeline data models."""

from enum import Enum


class RecordType(str, Enum):
    """Canonical record types for the pipeline."""

    STARTUP = "STARTUP"
    PRODUCT = "PRODUCT"
    RESEARCH_PAPER = "RESEARCH_PAPER"
    JOB = "JOB"
    NEWS = "NEWS"


class PricingModel(str, Enum):
    """Accepted pricing model values for products."""

    FREE = "FREE"
    FREEMIUM = "FREEMIUM"
    PAID = "PAID"
    ENTERPRISE = "ENTERPRISE"


class MatchMethod(str, Enum):
    """Entity resolution match methods."""

    EXACT = "exact"
    NORMALIZED = "normalized"
    ALIAS = "alias"
    FUZZY = "fuzzy"
    LLM = "llm"
    UNRESOLVED = "unresolved"
