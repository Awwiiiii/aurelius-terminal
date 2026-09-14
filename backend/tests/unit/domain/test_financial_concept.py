"""
tests.unit.domain.test_financial_concept
=========================================
Unit tests for FinancialConcept identity, canonical mapping, and conservative semantics.
"""

from aurelius.domain.entities.financials import (
    CanonicalConcept,
    FinancialConcept,
    StatementType,
)


def test_canonical_concept_mapped():
    """
    FinancialConcept correctly stores source concept and canonical concept.
    """
    concept = FinancialConcept(
        source_concept="Total Revenue",
        canonical_concept=CanonicalConcept.REVENUE,
        statement_type=StatementType.INCOME_STATEMENT,
        taxonomy="yahoo_finance",
    )
    assert concept.source_concept == "Total Revenue"
    assert concept.canonical_concept == CanonicalConcept.REVENUE
    assert concept.statement_type == StatementType.INCOME_STATEMENT
    assert concept.taxonomy == "yahoo_finance"


def test_unmapped_concept_retains_source_identity():
    """
    Unmapped concepts retain source label with canonical_concept = None.
    Never aggressively guessed.
    """
    concept = FinancialConcept(
        source_concept="Special Restructuring And Impairment Charges",
        canonical_concept=None,
        statement_type=StatementType.INCOME_STATEMENT,
    )
    assert concept.source_concept == "Special Restructuring And Impairment Charges"
    assert concept.canonical_concept is None


def test_ebitda_canonical_concept_is_source_reported_only():
    """
    EBITDA can only be mapped when reported directly by provider/source.
    It is never fabricated or calculated in M6.
    """
    ebitda_concept = FinancialConcept(
        source_concept="Normalized EBITDA",
        canonical_concept=CanonicalConcept.EBITDA,
        statement_type=StatementType.INCOME_STATEMENT,
    )
    assert ebitda_concept.canonical_concept == CanonicalConcept.EBITDA
