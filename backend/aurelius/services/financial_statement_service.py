"""
aurelius.services.financial_statement_service
==============================================
Application service orchestrating financial statement data retrieval, validation,
and tabular presentation matrix assembly.

Architecture:
  - Orchestration only: Sits between API transport and Domain/Providers.
  - Non-corporate enforcement: Validates that financial statements are only requested
    for corporate equities. Non-corporate instruments (ETFs, Indices) raise clean
    domain errors.
  - Decimal Preservation: Financial values remain exact Python Decimals throughout.
  - Matrix Representation: Assembles multi-period FinancialStatementMatrix strictly
    as a presentation/query structure without mutating underlying FinancialFact entities.
"""

import logging
from decimal import Decimal

from aurelius.domain.entities.enums import AssetType, Currency
from aurelius.domain.entities.financials import (
    CanonicalConcept,
    FinancialMatrixRow,
    FinancialPeriod,
    FinancialStatement,
    FinancialStatementMatrix,
    FiscalPeriodType,
    StatementType,
)
from aurelius.domain.errors import DataNotFoundError
from aurelius.domain.validation import validate_ticker
from aurelius.providers.base import MarketDataProvider

logger = logging.getLogger(__name__)

# Predefined canonical display order per statement type
CANONICAL_ORDER: dict[StatementType, list[CanonicalConcept]] = {
    StatementType.INCOME_STATEMENT: [
        CanonicalConcept.REVENUE,
        CanonicalConcept.COST_OF_REVENUE,
        CanonicalConcept.GROSS_PROFIT,
        CanonicalConcept.RESEARCH_AND_DEVELOPMENT,
        CanonicalConcept.SELLING_GENERAL_AND_ADMINISTRATIVE,
        CanonicalConcept.OPERATING_EXPENSES,
        CanonicalConcept.OPERATING_INCOME,
        CanonicalConcept.OTHER_INCOME_EXPENSE,
        CanonicalConcept.PRETAX_INCOME,
        CanonicalConcept.INCOME_TAX_EXPENSE,
        CanonicalConcept.NET_INCOME,
        CanonicalConcept.EBITDA,
    ],
    StatementType.BALANCE_SHEET: [
        CanonicalConcept.CASH_AND_EQUIVALENTS,
        CanonicalConcept.SHORT_TERM_INVESTMENTS,
        CanonicalConcept.ACCOUNTS_RECEIVABLE,
        CanonicalConcept.INVENTORY,
        CanonicalConcept.CURRENT_ASSETS,
        CanonicalConcept.PROPERTY_PLANT_EQUIPMENT,
        CanonicalConcept.GOODWILL,
        CanonicalConcept.INTANGIBLE_ASSETS,
        CanonicalConcept.TOTAL_ASSETS,
        CanonicalConcept.ACCOUNTS_PAYABLE,
        CanonicalConcept.CURRENT_LIABILITIES,
        CanonicalConcept.LONG_TERM_DEBT,
        CanonicalConcept.TOTAL_LIABILITIES,
        CanonicalConcept.STOCKHOLDERS_EQUITY,
    ],
    StatementType.CASH_FLOW: [
        CanonicalConcept.OPERATING_CASH_FLOW,
        CanonicalConcept.CAPITAL_EXPENDITURES,
        CanonicalConcept.INVESTING_CASH_FLOW,
        CanonicalConcept.FINANCING_CASH_FLOW,
        CanonicalConcept.NET_CHANGE_IN_CASH,
    ],
}


class FinancialStatementService:
    """
    Application service coordinating financial statement operations.
    """

    def __init__(self, provider: MarketDataProvider) -> None:
        self.provider = provider

    async def get_statements(
        self,
        ticker: str,
        statement_type: StatementType,
        frequency: FiscalPeriodType = FiscalPeriodType.ANNUAL,
    ) -> list[FinancialStatement]:
        """
        Retrieve financial statements for a ticker, enforcing corporate asset eligibility.
        """
        normalized_ticker = validate_ticker(ticker)

        # Confirm instrument exists and verify asset eligibility
        try:
            security = await self.provider.get_security(normalized_ticker)
            if security.asset_type not in (AssetType.EQUITY, AssetType.UNKNOWN):
                raise DataNotFoundError(
                    f"Financial statements are not reported for non-corporate instrument "
                    f"'{normalized_ticker}' ({security.asset_type.value}).",
                    ticker=normalized_ticker,
                )
        except DataNotFoundError:
            raise
        except Exception as exc:
            logger.warning(
                "Could not verify security eligibility for %s: %s",
                normalized_ticker,
                exc,
            )

        statements = await self.provider.get_financial_statements(
            normalized_ticker, statement_type, frequency
        )
        return statements

    async def get_statement_matrix(
        self,
        ticker: str,
        statement_type: StatementType,
        frequency: FiscalPeriodType = FiscalPeriodType.ANNUAL,
    ) -> FinancialStatementMatrix:
        """
        Build a multi-period presentation matrix for high-density tabular terminal display.
        Values remain exact Python Decimals (or None for missing).
        """
        normalized_ticker = validate_ticker(ticker)
        statements = await self.get_statements(
            normalized_ticker, statement_type, frequency
        )

        if not statements:
            return FinancialStatementMatrix(
                company_id=normalized_ticker,
                statement_type=statement_type,
                frequency=frequency,
                currency=Currency.USD,
                periods=[],
                rows=[],
            )

        # Collect unique periods sorted chronologically
        periods: list[FinancialPeriod] = [stmt.period for stmt in statements]
        period_keys: list[str] = [p.period_key for p in periods]

        # Aggregate facts across all statements
        reporting_currency: Currency | None = statements[0].currency

        # Key: (canonical_concept, source_concept)
        concept_facts: dict[
            tuple[CanonicalConcept | None, str], dict[str, Decimal]
        ] = {}

        for stmt in statements:
            p_key = stmt.period.period_key
            for fact in stmt.facts:
                key = (fact.concept.canonical_concept, fact.concept.source_concept)
                if key not in concept_facts:
                    concept_facts[key] = {}
                concept_facts[key][p_key] = fact.value

        # Build rows: canonical concepts first in order, then unmapped rows
        canonical_hierarchy = CANONICAL_ORDER.get(statement_type, [])
        rows: list[FinancialMatrixRow] = []

        # 1. Canonical rows
        for canon in canonical_hierarchy:
            # Find matching items in concept_facts
            matching_keys = [k for k in concept_facts if k[0] == canon]
            if matching_keys:
                # Use the primary source label
                primary_key = matching_keys[0]
                values = concept_facts[primary_key]
                row_values: dict[str, Decimal | None] = {
                    pk: values.get(pk) for pk in period_keys
                }
                display_label = canon.value.replace("_", " ").title()
                rows.append(
                    FinancialMatrixRow(
                        concept_key=canon.value,
                        display_name=display_label,
                        canonical_concept=canon,
                        is_canonical=True,
                        values_by_period=row_values,
                    )
                )

        # 2. Unmapped / Detailed Provider rows
        for (canon, source_label), values in concept_facts.items():
            if canon is None:
                row_values = {pk: values.get(pk) for pk in period_keys}
                rows.append(
                    FinancialMatrixRow(
                        concept_key=source_label,
                        display_name=source_label,
                        canonical_concept=None,
                        is_canonical=False,
                        values_by_period=row_values,
                    )
                )

        return FinancialStatementMatrix(
            company_id=normalized_ticker,
            statement_type=statement_type,
            frequency=frequency,
            currency=reporting_currency,
            periods=periods,
            rows=rows,
        )


_statement_service_instance: FinancialStatementService | None = None


def get_financial_statement_service() -> FinancialStatementService:
    """
    FastAPI dependency provider for FinancialStatementService.
    """
    global _statement_service_instance
    if _statement_service_instance is None:
        from aurelius.providers.registry import get_market_data_provider

        _statement_service_instance = FinancialStatementService(
            provider=get_market_data_provider()
        )
    return _statement_service_instance
