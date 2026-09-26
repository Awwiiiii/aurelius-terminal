"""
aurelius.domain.entities.financials
===================================
Domain models and canonical taxonomies for financial statement infrastructure.

Domain Principles:
  - Strict Period Semantics:
      * Balance Sheet items are strictly INSTANT (point-in-time).
      * Income Statement and Cash Flow items are strictly DURATION (interval).
  - Exact Decimal Arithmetic:
      * Financial fact values strictly use Python Decimal to avoid IEEE-754 floating-point inaccuracies.
  - Orthogonal Measurement:
      * unit (CURRENCY, SHARES, RATIO, PERCENT), currency (ISO-4217 Currency), and
        scale (UNITS, THOUSANDS, MILLIONS, BILLIONS) are strictly separated and validated.
  - Date Provenance:
      * filing_date and report_period_end are semantically distinct and never collapsed.
  - Conservative Canonical Normalization:
      * Unmapped source items retain their raw provider concept name with canonical_concept = None.
      * CanonicalConcept.EBITDA is strictly mapped only when directly reported by the provider.
        It is NEVER calculated or synthesized in M6.
  - No Plausible Fabrication:
      * Missing financial line items remain None or omitted. Missing is NEVER converted to zero.
"""

from datetime import date
from decimal import Decimal
from enum import StrEnum
from typing import Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from aurelius.domain.entities.enums import Currency

# =============================================================================
# ENUMERATIONS
# =============================================================================


class PeriodType(StrEnum):
    """
    Measurement temporal type for a financial fact or statement.
    INSTANT: Measured at a single point in time (e.g., Balance Sheet cash).
    DURATION: Measured across a time interval (e.g., Income Statement revenue).
    """

    INSTANT = "INSTANT"
    DURATION = "DURATION"


class StatementType(StrEnum):
    """
    Core financial statement classification.
    """

    INCOME_STATEMENT = "INCOME_STATEMENT"
    BALANCE_SHEET = "BALANCE_SHEET"
    CASH_FLOW = "CASH_FLOW"


class FiscalPeriodType(StrEnum):
    """
    Reporting frequency.
    """

    ANNUAL = "ANNUAL"
    QUARTERLY = "QUARTERLY"
    TTM = "TTM"


class FiscalPeriodLabel(StrEnum):
    """
    Authoritative or derived fiscal period identifier.
    """

    FY = "FY"
    Q1 = "Q1"
    Q2 = "Q2"
    Q3 = "Q3"
    Q4 = "Q4"
    TTM = "TTM"


class Unit(StrEnum):
    """
    Measurement unit classification.
    """

    CURRENCY = "CURRENCY"
    SHARES = "SHARES"
    RATIO = "RATIO"
    PERCENT = "PERCENT"


class Scale(StrEnum):
    """
    Magnitude multiplier applied to the reported value.
    UNITS: 10^0
    THOUSANDS: 10^3
    MILLIONS: 10^6
    BILLIONS: 10^9
    """

    UNITS = "UNITS"
    THOUSANDS = "THOUSANDS"
    MILLIONS = "MILLIONS"
    BILLIONS = "BILLIONS"

    @property
    def multiplier(self) -> Decimal:
        match self:
            case Scale.UNITS:
                return Decimal("1")
            case Scale.THOUSANDS:
                return Decimal("1000")
            case Scale.MILLIONS:
                return Decimal("1000000")
            case Scale.BILLIONS:
                return Decimal("1000000000")


class CanonicalConcept(StrEnum):
    """
    Standardized, conservative financial concept taxonomy for AURELIUS.
    Maps vendor-specific and XBRL line items to canonical research concepts.
    """

    # --- Income Statement ---
    REVENUE = "REVENUE"
    COST_OF_REVENUE = "COST_OF_REVENUE"
    GROSS_PROFIT = "GROSS_PROFIT"
    OPERATING_EXPENSES = "OPERATING_EXPENSES"
    RESEARCH_AND_DEVELOPMENT = "RESEARCH_AND_DEVELOPMENT"
    SELLING_GENERAL_AND_ADMINISTRATIVE = "SELLING_GENERAL_AND_ADMINISTRATIVE"
    OPERATING_INCOME = "OPERATING_INCOME"
    OTHER_INCOME_EXPENSE = "OTHER_INCOME_EXPENSE"
    PRETAX_INCOME = "PRETAX_INCOME"
    INCOME_TAX_EXPENSE = "INCOME_TAX_EXPENSE"
    NET_INCOME = "NET_INCOME"
    EBITDA = "EBITDA"  # Only populated when directly reported by source

    # --- Balance Sheet ---
    CASH_AND_EQUIVALENTS = "CASH_AND_EQUIVALENTS"
    SHORT_TERM_INVESTMENTS = "SHORT_TERM_INVESTMENTS"
    ACCOUNTS_RECEIVABLE = "ACCOUNTS_RECEIVABLE"
    INVENTORY = "INVENTORY"
    CURRENT_ASSETS = "CURRENT_ASSETS"
    PROPERTY_PLANT_EQUIPMENT = "PROPERTY_PLANT_EQUIPMENT"
    GOODWILL = "GOODWILL"
    INTANGIBLE_ASSETS = "INTANGIBLE_ASSETS"
    TOTAL_ASSETS = "TOTAL_ASSETS"
    ACCOUNTS_PAYABLE = "ACCOUNTS_PAYABLE"
    CURRENT_LIABILITIES = "CURRENT_LIABILITIES"
    LONG_TERM_DEBT = "LONG_TERM_DEBT"
    TOTAL_LIABILITIES = "TOTAL_LIABILITIES"
    STOCKHOLDERS_EQUITY = "STOCKHOLDERS_EQUITY"

    # --- Cash Flow Statement ---
    OPERATING_CASH_FLOW = "OPERATING_CASH_FLOW"
    CAPITAL_EXPENDITURES = "CAPITAL_EXPENDITURES"
    INVESTING_CASH_FLOW = "INVESTING_CASH_FLOW"
    FINANCING_CASH_FLOW = "FINANCING_CASH_FLOW"
    NET_CHANGE_IN_CASH = "NET_CHANGE_IN_CASH"


# =============================================================================
# DOMAIN ENTITIES
# =============================================================================


class Filing(BaseModel):
    """
    Representation of the source filing or provider disclosure document.
    """

    model_config = ConfigDict(frozen=True)

    filing_id: str = Field(
        ..., description="Deterministic unique identifier for this filing record."
    )
    company_id: str = Field(
        ...,
        description="Listing ticker or company identifier associated with this filing.",
    )
    accession_number: str | None = Field(
        default=None,
        description="Official SEC EDGAR accession number (e.g., '0000320193-23-000106'), if known.",
    )
    form_type: str | None = Field(
        default=None,
        description="Filing form code (e.g., '10-K', '10-Q', '20-F', '8-K'), if known.",
    )
    filing_date: date | None = Field(
        default=None,
        description="Calendar date on which the filing was submitted/accepted. Distinct from report_period_end.",
    )
    report_period_end: date = Field(
        ...,
        description="Fiscal period cutoff date covered by this filing report.",
    )
    source: str = Field(
        ...,
        description="Primary source or provider supplying this filing (e.g. 'yahoo_finance', 'sec_edgar').",
    )


class FinancialPeriod(BaseModel):
    """
    Temporal boundaries and fiscal metadata for a financial fact or statement.
    """

    model_config = ConfigDict(frozen=True)

    period_type: PeriodType = Field(
        ...,
        description="Temporal measurement nature: INSTANT (point-in-time) vs DURATION (interval).",
    )
    instant_date: date | None = Field(
        default=None,
        description="Point-in-time date for INSTANT periods (e.g., Balance Sheet date).",
    )
    start_date: date | None = Field(
        default=None,
        description="Start date of duration interval for DURATION periods.",
    )
    end_date: date | None = Field(
        default=None,
        description="End date of duration interval for DURATION periods.",
    )
    fiscal_year: int | None = Field(
        default=None,
        description="Reported or safely derived fiscal year (e.g., 2024).",
    )
    fiscal_period: FiscalPeriodLabel | None = Field(
        default=None,
        description="Fiscal period label (FY, Q1, Q2, Q3, Q4).",
    )
    is_period_label_source_reported: bool = Field(
        default=False,
        description="True if fiscal_period was reported by the source; False if derived.",
    )
    calendar_year: int | None = Field(
        default=None,
        description="Calendar year corresponding to the period cutoff.",
    )

    @model_validator(mode="after")
    def validate_period_bounds(self) -> Self:
        if self.period_type == PeriodType.INSTANT:
            if self.instant_date is None:
                raise ValueError(
                    "FinancialPeriod of type INSTANT requires instant_date."
                )
            if self.end_date is not None:
                raise ValueError(
                    "FinancialPeriod of type INSTANT cannot have end_date."
                )
            if self.start_date is not None:
                raise ValueError(
                    "FinancialPeriod of type INSTANT cannot have start_date."
                )
        elif self.period_type == PeriodType.DURATION:
            if self.end_date is None:
                raise ValueError("FinancialPeriod of type DURATION requires end_date.")
            if self.instant_date is not None:
                raise ValueError(
                    "FinancialPeriod of type DURATION cannot have instant_date."
                )
            if self.start_date is not None and self.start_date > self.end_date:
                raise ValueError(
                    f"FinancialPeriod start_date ({self.start_date}) cannot be after end_date ({self.end_date})."
                )
        return self

    @property
    def period_key(self) -> str:
        """
        Unique deterministic string key representing this period's cutoff date.
        """
        if self.period_type == PeriodType.INSTANT and self.instant_date:
            return self.instant_date.isoformat()
        if self.end_date:
            return self.end_date.isoformat()
        return "unknown_period"


class FinancialConcept(BaseModel):
    """
    Identity and classification of a reported financial line item.
    """

    model_config = ConfigDict(frozen=True)

    source_concept: str = Field(
        ...,
        description="Raw line-item label or XBRL tag as reported by the provider (e.g., 'Total Revenue').",
    )
    canonical_concept: CanonicalConcept | None = Field(
        default=None,
        description="Normalized AURELIUS canonical concept. None if concept cannot be safely mapped.",
    )
    statement_type: StatementType = Field(
        ...,
        description="The financial statement this concept belongs to.",
    )
    taxonomy: str | None = Field(
        default=None,
        description="Accounting or provider taxonomy (e.g., 'yahoo_finance', 'us-gaap', 'ifrs-full').",
    )


class FinancialFact(BaseModel):
    """
    Authoritative reported financial fact observation with complete provenance.
    """

    model_config = ConfigDict(frozen=True)

    fact_id: str = Field(
        ...,
        description="Deterministic unique hash/id for this fact observation.",
    )
    company_id: str = Field(
        ...,
        description="Listing ticker or company identifier.",
    )
    concept: FinancialConcept = Field(
        ...,
        description="Reported and canonical concept metadata.",
    )
    value: Decimal = Field(
        ...,
        description="Exact reported financial numeric value (strictly Decimal).",
    )
    unit: Unit = Field(
        ...,
        description="Measurement unit: CURRENCY, SHARES, RATIO, PERCENT.",
    )
    currency: Currency | None = Field(
        default=None,
        description="ISO-4217 Currency code. Required when unit == Unit.CURRENCY; must be None when unit == SHARES.",
    )
    scale: Scale = Field(
        default=Scale.UNITS,
        description="Magnitude multiplier for the value (UNITS, THOUSANDS, MILLIONS, BILLIONS).",
    )
    period: FinancialPeriod = Field(
        ...,
        description="Temporal period specification (INSTANT vs DURATION).",
    )
    filing: Filing | None = Field(
        default=None,
        description="Source filing reference, if available.",
    )
    dimensions: dict[str, str] = Field(
        default_factory=dict,
        description="Dimensional disaggregation context (e.g. segment, geography, class).",
    )
    provenance: dict[str, str] = Field(
        default_factory=dict,
        description="Audit metadata (provider, ingestion_timestamp, source_field).",
    )
    is_restated: bool = Field(
        default=False,
        description="Flags whether this observation represents a restated/amended value.",
    )

    @model_validator(mode="after")
    def validate_unit_and_currency(self) -> Self:
        if self.unit == Unit.CURRENCY:
            if self.currency is None or self.currency == Currency.UNKNOWN:
                raise ValueError(
                    "FinancialFact with unit=CURRENCY must specify a known currency."
                )
        elif (
            self.unit in (Unit.SHARES, Unit.RATIO, Unit.PERCENT)
            and self.currency is not None
        ):
            raise ValueError(
                f"FinancialFact with unit={self.unit.value} must have currency=None."
            )
        return self


class FinancialStatement(BaseModel):
    """
    Authoritative collection of financial facts representing a single reported financial statement.
    """

    model_config = ConfigDict(frozen=True)

    statement_id: str = Field(
        ...,
        description="Deterministic identifier for this statement instance.",
    )
    company_id: str = Field(
        ...,
        description="Listing ticker or company identifier.",
    )
    statement_type: StatementType = Field(
        ...,
        description="INCOME_STATEMENT, BALANCE_SHEET, or CASH_FLOW.",
    )
    frequency: FiscalPeriodType = Field(
        default=FiscalPeriodType.ANNUAL,
        description="Reporting frequency: ANNUAL or QUARTERLY.",
    )
    period: FinancialPeriod = Field(
        ...,
        description="Reporting period covered by this statement.",
    )
    facts: list[FinancialFact] = Field(
        ...,
        description="Collection of reported financial facts for this statement and period.",
    )
    currency: Currency | None = Field(
        default=None,
        description="Primary reporting currency for the statement.",
    )
    filing: Filing | None = Field(
        default=None,
        description="Filing disclosure metadata, if available.",
    )


# =============================================================================
# PRESENTATION / QUERY STRUCTURES
# =============================================================================


class FinancialMatrixRow(BaseModel):
    """
    A single row in the presentation matrix for tabular multi-period display.
    """

    model_config = ConfigDict(frozen=True)

    concept_key: str = Field(
        ..., description="Canonical concept name or normalized source concept."
    )
    display_name: str = Field(..., description="Human-readable concept label.")
    canonical_concept: CanonicalConcept | None = Field(
        default=None, description="AURELIUS canonical concept if mapped, else None."
    )
    is_canonical: bool = Field(
        default=False, description="True if mapped to a canonical concept."
    )
    values_by_period: dict[str, Decimal | None] = Field(
        default_factory=dict,
        description="Period key mapped to exact reported Decimal value, or None if missing.",
    )


class FinancialStatementMatrix(BaseModel):
    """
    Multi-period query/presentation view for high-density tabular terminal display.
    Strictly a presentation structure; does not replace FinancialStatement or FinancialFact.
    """

    model_config = ConfigDict(frozen=True)

    company_id: str
    statement_type: StatementType
    frequency: FiscalPeriodType
    currency: Currency | None = None
    periods: list[FinancialPeriod] = Field(
        default_factory=list,
        description="Chronologically sorted periods represented in the matrix columns.",
    )
    rows: list[FinancialMatrixRow] = Field(
        default_factory=list,
        description="Ordered line items.",
    )
