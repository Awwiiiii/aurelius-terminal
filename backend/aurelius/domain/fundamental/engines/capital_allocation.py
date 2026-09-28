"""
aurelius.domain.fundamental.engines.capital_allocation
======================================================
Pure calculation engine for capital allocation and shareholder yield metrics:
CFO, CapEx, Dividends, Stock Repurchases, Stock Issuances, Debt Flows, M&A,
and Market-Cap-relative Yields.

Standards:
  - Outflows (CapEx, Dividends Paid, Stock Repurchases, Debt Repayments) are
    strictly normalized to positive economic magnitudes (|val|).
  - Inflows (Stock Issuances, Debt Issuances) are strictly positive magnitudes.
  - Net Debt Issued = Debt Issued - Debt Repaid (positive = net borrowing,
    negative = net de-leveraging).
  - Yields (Dividend, Buyback, Gross Shareholder, Net Shareholder) divide by Market Capitalization.
  - Missing facts are NEVER converted to zero unless explicitly established.
  - Exact Decimal arithmetic with full audit provenance.
"""

from decimal import Decimal

from aurelius.domain.entities.financials import (
    FinancialPeriod,
    StatementType,
    Unit,
)
from aurelius.domain.fundamental.engines.cash_flow import CashFlowEngine
from aurelius.domain.fundamental.enums import (
    DiagnosticCode,
    FundamentalMetricId,
    MetricCategory,
    MetricStatus,
)
from aurelius.domain.fundamental.models import (
    MetricDiagnostic,
    MetricProvenance,
    MetricResult,
)
from aurelius.domain.fundamental.period_matching import MultiPeriodFactStore


class CapitalAllocationEngine:
    """
    Engine calculating capital deployment, financing flows, and shareholder return yields.
    """

    METHODOLOGY_VERSION = "1.0.0"

    @classmethod
    def calculate_operating_cash_flow(
        cls,
        period: FinancialPeriod,
        fact_store: MultiPeriodFactStore,
    ) -> MetricResult:
        """
        Retrieve canonical Operating Cash Flow (CFO).
        """
        return CashFlowEngine.calculate_operating_cash_flow(period, fact_store)

    @classmethod
    def calculate_capital_expenditures(
        cls,
        period: FinancialPeriod,
        fact_store: MultiPeriodFactStore,
    ) -> MetricResult:
        """
        Retrieve Capital Expenditures normalized to positive economic magnitude.
        """
        return CashFlowEngine.calculate_capital_expenditures(period, fact_store)

    @classmethod
    def calculate_dividends_paid(
        cls,
        period: FinancialPeriod,
        fact_store: MultiPeriodFactStore,
    ) -> MetricResult:
        """
        Retrieve cash dividends paid normalized to positive economic magnitude (|val|).
        """
        fact = fact_store.get_source_fact(
            StatementType.CASH_FLOW,
            [
                "Cash Dividends Paid",
                "Common Stock Dividend Paid",
                "Payment Of Dividends & Other Distributions",
            ],
            period.period_key,
        )
        if fact is None:
            return MetricResult(
                metric_id=FundamentalMetricId.DIVIDENDS_PAID,
                category=MetricCategory.CASH_FLOW,
                status=MetricStatus.UNAVAILABLE,
                value=None,
                unit=Unit.CURRENCY,
                currency=None,
                period=period,
                diagnostics=[
                    MetricDiagnostic(
                        code=DiagnosticCode.MISSING_REQUIRED_FACT,
                        message="Dividends paid line item is absent from cash flow statement.",
                        details={
                            "period": period.period_key,
                            "concept": "DIVIDENDS_PAID",
                        },
                    )
                ],
                provenance=MetricProvenance(
                    formula_id="FORMULA_DIVIDENDS_PAID_MAGNITUDE",
                    methodology_version=cls.METHODOLOGY_VERSION,
                    source_concepts=["Cash Dividends Paid"],
                    source_periods=[period.period_key],
                ),
            )

        magnitude = abs(fact.value)
        return MetricResult(
            metric_id=FundamentalMetricId.DIVIDENDS_PAID,
            category=MetricCategory.CASH_FLOW,
            status=MetricStatus.VALID,
            value=magnitude,
            unit=Unit.CURRENCY,
            currency=fact.currency,
            period=period,
            diagnostics=[],
            provenance=MetricProvenance(
                formula_id="FORMULA_DIVIDENDS_PAID_MAGNITUDE",
                methodology_version=cls.METHODOLOGY_VERSION,
                source_fact_ids=[fact.fact_id],
                source_concepts=[fact.concept.source_concept],
                source_periods=[period.period_key],
                methodology_notes=f"Reported value was {fact.value}; normalized to positive magnitude {magnitude}.",
            ),
        )

    @classmethod
    def calculate_stock_repurchases(
        cls,
        period: FinancialPeriod,
        fact_store: MultiPeriodFactStore,
    ) -> MetricResult:
        """
        Retrieve stock repurchases (buybacks) normalized to positive magnitude (|val|).
        """
        fact = fact_store.get_source_fact(
            StatementType.CASH_FLOW,
            [
                "Repurchase Of Capital Stock",
                "Common Stock Payments",
                "Purchase Of Treasury Stock",
            ],
            period.period_key,
        )
        if fact is None:
            return MetricResult(
                metric_id=FundamentalMetricId.STOCK_REPURCHASES,
                category=MetricCategory.CASH_FLOW,
                status=MetricStatus.UNAVAILABLE,
                value=None,
                unit=Unit.CURRENCY,
                currency=None,
                period=period,
                diagnostics=[
                    MetricDiagnostic(
                        code=DiagnosticCode.MISSING_REQUIRED_FACT,
                        message="Stock repurchases line item is absent from cash flow statement.",
                        details={
                            "period": period.period_key,
                            "concept": "STOCK_REPURCHASES",
                        },
                    )
                ],
                provenance=MetricProvenance(
                    formula_id="FORMULA_STOCK_REPURCHASES_MAGNITUDE",
                    methodology_version=cls.METHODOLOGY_VERSION,
                    source_concepts=["Repurchase Of Capital Stock"],
                    source_periods=[period.period_key],
                ),
            )

        magnitude = abs(fact.value)
        return MetricResult(
            metric_id=FundamentalMetricId.STOCK_REPURCHASES,
            category=MetricCategory.CASH_FLOW,
            status=MetricStatus.VALID,
            value=magnitude,
            unit=Unit.CURRENCY,
            currency=fact.currency,
            period=period,
            diagnostics=[],
            provenance=MetricProvenance(
                formula_id="FORMULA_STOCK_REPURCHASES_MAGNITUDE",
                methodology_version=cls.METHODOLOGY_VERSION,
                source_fact_ids=[fact.fact_id],
                source_concepts=[fact.concept.source_concept],
                source_periods=[period.period_key],
                methodology_notes=f"Reported value was {fact.value}; normalized to positive magnitude {magnitude}.",
            ),
        )

    @classmethod
    def calculate_stock_issuances(
        cls,
        period: FinancialPeriod,
        fact_store: MultiPeriodFactStore,
    ) -> MetricResult:
        """
        Retrieve proceeds from issuance of common stock (positive inflow magnitude).
        """
        fact = fact_store.get_source_fact(
            StatementType.CASH_FLOW,
            [
                "Issuance Of Capital Stock",
                "Common Stock Issuance",
            ],
            period.period_key,
        )
        if fact is None:
            return MetricResult(
                metric_id=FundamentalMetricId.STOCK_ISSUANCES,
                category=MetricCategory.CASH_FLOW,
                status=MetricStatus.UNAVAILABLE,
                value=None,
                unit=Unit.CURRENCY,
                currency=None,
                period=period,
                diagnostics=[
                    MetricDiagnostic(
                        code=DiagnosticCode.MISSING_REQUIRED_FACT,
                        message="Stock issuance line item is absent from cash flow statement.",
                        details={
                            "period": period.period_key,
                            "concept": "STOCK_ISSUANCES",
                        },
                    )
                ],
                provenance=MetricProvenance(
                    formula_id="FORMULA_STOCK_ISSUANCES_MAGNITUDE",
                    methodology_version=cls.METHODOLOGY_VERSION,
                    source_concepts=["Issuance Of Capital Stock"],
                    source_periods=[period.period_key],
                ),
            )

        magnitude = abs(fact.value)
        return MetricResult(
            metric_id=FundamentalMetricId.STOCK_ISSUANCES,
            category=MetricCategory.CASH_FLOW,
            status=MetricStatus.VALID,
            value=magnitude,
            unit=Unit.CURRENCY,
            currency=fact.currency,
            period=period,
            diagnostics=[],
            provenance=MetricProvenance(
                formula_id="FORMULA_STOCK_ISSUANCES_MAGNITUDE",
                methodology_version=cls.METHODOLOGY_VERSION,
                source_fact_ids=[fact.fact_id],
                source_concepts=[fact.concept.source_concept],
                source_periods=[period.period_key],
                methodology_notes=f"Reported stock issuance: {magnitude}.",
            ),
        )

    @classmethod
    def calculate_debt_issued(
        cls,
        period: FinancialPeriod,
        fact_store: MultiPeriodFactStore,
    ) -> MetricResult:
        """
        Retrieve cash received from debt issuance (positive inflow magnitude).
        """
        fact = fact_store.get_source_fact(
            StatementType.CASH_FLOW,
            [
                "Issuance Of Debt",
                "Long Term Debt Issuance",
            ],
            period.period_key,
        )
        if fact is None:
            return MetricResult(
                metric_id=FundamentalMetricId.DEBT_ISSUED,
                category=MetricCategory.CASH_FLOW,
                status=MetricStatus.UNAVAILABLE,
                value=None,
                unit=Unit.CURRENCY,
                currency=None,
                period=period,
                diagnostics=[
                    MetricDiagnostic(
                        code=DiagnosticCode.MISSING_REQUIRED_FACT,
                        message="Debt issuance line item is absent from cash flow statement.",
                        details={"period": period.period_key, "concept": "DEBT_ISSUED"},
                    )
                ],
                provenance=MetricProvenance(
                    formula_id="FORMULA_DEBT_ISSUED_MAGNITUDE",
                    methodology_version=cls.METHODOLOGY_VERSION,
                    source_concepts=["Issuance Of Debt"],
                    source_periods=[period.period_key],
                ),
            )

        magnitude = abs(fact.value)
        return MetricResult(
            metric_id=FundamentalMetricId.DEBT_ISSUED,
            category=MetricCategory.CASH_FLOW,
            status=MetricStatus.VALID,
            value=magnitude,
            unit=Unit.CURRENCY,
            currency=fact.currency,
            period=period,
            diagnostics=[],
            provenance=MetricProvenance(
                formula_id="FORMULA_DEBT_ISSUED_MAGNITUDE",
                methodology_version=cls.METHODOLOGY_VERSION,
                source_fact_ids=[fact.fact_id],
                source_concepts=[fact.concept.source_concept],
                source_periods=[period.period_key],
            ),
        )

    @classmethod
    def calculate_debt_repaid(
        cls,
        period: FinancialPeriod,
        fact_store: MultiPeriodFactStore,
    ) -> MetricResult:
        """
        Retrieve cash paid to retire debt (normalized to positive economic magnitude).
        """
        fact = fact_store.get_source_fact(
            StatementType.CASH_FLOW,
            [
                "Repayment Of Debt",
                "Long Term Debt Payments",
            ],
            period.period_key,
        )
        if fact is None:
            return MetricResult(
                metric_id=FundamentalMetricId.DEBT_REPAID,
                category=MetricCategory.CASH_FLOW,
                status=MetricStatus.UNAVAILABLE,
                value=None,
                unit=Unit.CURRENCY,
                currency=None,
                period=period,
                diagnostics=[
                    MetricDiagnostic(
                        code=DiagnosticCode.MISSING_REQUIRED_FACT,
                        message="Debt repayment line item is absent from cash flow statement.",
                        details={"period": period.period_key, "concept": "DEBT_REPAID"},
                    )
                ],
                provenance=MetricProvenance(
                    formula_id="FORMULA_DEBT_REPAID_MAGNITUDE",
                    methodology_version=cls.METHODOLOGY_VERSION,
                    source_concepts=["Repayment Of Debt"],
                    source_periods=[period.period_key],
                ),
            )

        magnitude = abs(fact.value)
        return MetricResult(
            metric_id=FundamentalMetricId.DEBT_REPAID,
            category=MetricCategory.CASH_FLOW,
            status=MetricStatus.VALID,
            value=magnitude,
            unit=Unit.CURRENCY,
            currency=fact.currency,
            period=period,
            diagnostics=[],
            provenance=MetricProvenance(
                formula_id="FORMULA_DEBT_REPAID_MAGNITUDE",
                methodology_version=cls.METHODOLOGY_VERSION,
                source_fact_ids=[fact.fact_id],
                source_concepts=[fact.concept.source_concept],
                source_periods=[period.period_key],
                methodology_notes=f"Reported value was {fact.value}; normalized to positive magnitude {magnitude}.",
            ),
        )

    @classmethod
    def calculate_net_debt_issued(
        cls,
        period: FinancialPeriod,
        fact_store: MultiPeriodFactStore,
    ) -> MetricResult:
        """
        Calculate Net Debt Issued: Debt Issued - Debt Repaid.
        Positive = net borrowing (leverage increase).
        Negative = net debt reduction (de-leveraging).
        """
        issued_res = cls.calculate_debt_issued(period, fact_store)
        repaid_res = cls.calculate_debt_repaid(period, fact_store)

        if (
            issued_res.status == MetricStatus.VALID
            and repaid_res.status == MetricStatus.VALID
            and issued_res.value is not None
            and repaid_res.value is not None
        ):
            net_val = issued_res.value - repaid_res.value
            return MetricResult(
                metric_id=FundamentalMetricId.NET_DEBT_ISSUED,
                category=MetricCategory.CASH_FLOW,
                status=MetricStatus.VALID,
                value=net_val,
                unit=Unit.CURRENCY,
                currency=issued_res.currency,
                period=period,
                diagnostics=[],
                provenance=MetricProvenance(
                    formula_id="FORMULA_NET_DEBT_ISSUED_GROSS_DIFFERENCE",
                    methodology_version=cls.METHODOLOGY_VERSION,
                    source_fact_ids=issued_res.provenance.source_fact_ids
                    + repaid_res.provenance.source_fact_ids,
                    source_concepts=["Issuance Of Debt", "Repayment Of Debt"],
                    source_periods=[period.period_key],
                    methodology_notes=f"Net Debt Issued = Issued ({issued_res.value}) - Repaid ({repaid_res.value}) = {net_val}.",
                ),
            )

        # Fallback to reported aggregate "Net Issuance Payments Of Debt"
        net_debt_fact = fact_store.get_source_fact(
            StatementType.CASH_FLOW,
            ["Net Issuance Payments Of Debt"],
            period.period_key,
        )
        if net_debt_fact is not None:
            return MetricResult(
                metric_id=FundamentalMetricId.NET_DEBT_ISSUED,
                category=MetricCategory.CASH_FLOW,
                status=MetricStatus.VALID,
                value=net_debt_fact.value,
                unit=Unit.CURRENCY,
                currency=net_debt_fact.currency,
                period=period,
                diagnostics=[],
                provenance=MetricProvenance(
                    formula_id="FORMULA_NET_DEBT_ISSUED_REPORTED_AGGREGATE",
                    methodology_version=cls.METHODOLOGY_VERSION,
                    source_fact_ids=[net_debt_fact.fact_id],
                    source_concepts=[net_debt_fact.concept.source_concept],
                    source_periods=[period.period_key],
                    methodology_notes="Net Debt Issued sourced from reported composite aggregate.",
                ),
            )

        return MetricResult(
            metric_id=FundamentalMetricId.NET_DEBT_ISSUED,
            category=MetricCategory.CASH_FLOW,
            status=MetricStatus.UNAVAILABLE,
            value=None,
            unit=Unit.CURRENCY,
            currency=None,
            period=period,
            diagnostics=[
                MetricDiagnostic(
                    code=DiagnosticCode.MISSING_REQUIRED_FACT,
                    message="Net debt flows cannot be determined from debt issuance/repayment line items.",
                    details={"period": period.period_key},
                )
            ],
            provenance=MetricProvenance(
                formula_id="FORMULA_NET_DEBT_ISSUED_GROSS_DIFFERENCE",
                methodology_version=cls.METHODOLOGY_VERSION,
                source_concepts=["Issuance Of Debt", "Repayment Of Debt"],
                source_periods=[period.period_key],
            ),
        )

    @classmethod
    def calculate_ma_investment(
        cls,
        period: FinancialPeriod,
        fact_store: MultiPeriodFactStore,
    ) -> MetricResult:
        """
        Retrieve M&A investment (Acquisition of Business) where reliably reported.
        """
        fact = fact_store.get_source_fact(
            StatementType.CASH_FLOW,
            [
                "Acquisition Of Business",
                "Net Business Purchase And Sale",
            ],
            period.period_key,
        )
        if fact is None:
            return MetricResult(
                metric_id=FundamentalMetricId.M_AND_A_INVESTMENT,
                category=MetricCategory.CASH_FLOW,
                status=MetricStatus.UNAVAILABLE,
                value=None,
                unit=Unit.CURRENCY,
                currency=None,
                period=period,
                diagnostics=[
                    MetricDiagnostic(
                        code=DiagnosticCode.M_AND_A_DATA_UNAVAILABLE,
                        message="M&A acquisition cash flow is not separately disclosed by vendor.",
                        details={"period": period.period_key},
                    )
                ],
                provenance=MetricProvenance(
                    formula_id="FORMULA_MA_INVESTMENT_MAGNITUDE",
                    methodology_version=cls.METHODOLOGY_VERSION,
                    source_concepts=["Acquisition Of Business"],
                    source_periods=[period.period_key],
                    methodology_notes="M&A data omitted by provider; not synthesized.",
                ),
            )

        magnitude = abs(fact.value)
        return MetricResult(
            metric_id=FundamentalMetricId.M_AND_A_INVESTMENT,
            category=MetricCategory.CASH_FLOW,
            status=MetricStatus.VALID,
            value=magnitude,
            unit=Unit.CURRENCY,
            currency=fact.currency,
            period=period,
            diagnostics=[],
            provenance=MetricProvenance(
                formula_id="FORMULA_MA_INVESTMENT_MAGNITUDE",
                methodology_version=cls.METHODOLOGY_VERSION,
                source_fact_ids=[fact.fact_id],
                source_concepts=[fact.concept.source_concept],
                source_periods=[period.period_key],
                methodology_notes=f"Reported M&A investment magnitude: {magnitude}.",
            ),
        )

    # -------------------------------------------------------------------------
    # Shareholder Yields (Market-Cap Relative)
    # -------------------------------------------------------------------------

    @classmethod
    def calculate_dividend_yield(
        cls,
        period: FinancialPeriod,
        fact_store: MultiPeriodFactStore,
        market_cap: Decimal | None,
    ) -> MetricResult:
        """
        Calculate Dividend Yield: Dividends Paid / Market Capitalization.
        """
        div_res = cls.calculate_dividends_paid(period, fact_store)
        return cls._compute_yield(
            metric_id=FundamentalMetricId.DIVIDEND_YIELD,
            period=period,
            numerator_res=div_res,
            market_cap=market_cap,
            formula_id="FORMULA_DIVIDEND_YIELD_V1",
            notes="Dividend Yield = Dividends Paid / Market Capitalization.",
        )

    @classmethod
    def calculate_buyback_yield(
        cls,
        period: FinancialPeriod,
        fact_store: MultiPeriodFactStore,
        market_cap: Decimal | None,
    ) -> MetricResult:
        """
        Calculate Buyback Yield: Stock Repurchases / Market Capitalization.
        """
        buyback_res = cls.calculate_stock_repurchases(period, fact_store)
        return cls._compute_yield(
            metric_id=FundamentalMetricId.BUYBACK_YIELD,
            period=period,
            numerator_res=buyback_res,
            market_cap=market_cap,
            formula_id="FORMULA_BUYBACK_YIELD_V1",
            notes="Buyback Yield = Stock Repurchases / Market Capitalization.",
        )

    @classmethod
    def calculate_shareholder_yield(
        cls,
        period: FinancialPeriod,
        fact_store: MultiPeriodFactStore,
        market_cap: Decimal | None,
    ) -> MetricResult:
        """
        Calculate Gross Shareholder Yield: (Dividends Paid + Stock Repurchases) / Market Cap.
        """
        div_res = cls.calculate_dividends_paid(period, fact_store)
        rep_res = cls.calculate_stock_repurchases(period, fact_store)

        if (
            div_res.status != MetricStatus.VALID
            or rep_res.status != MetricStatus.VALID
            or div_res.value is None
            or rep_res.value is None
        ):
            missing_items = []
            if div_res.status != MetricStatus.VALID:
                missing_items.append("Dividends Paid")
            if rep_res.status != MetricStatus.VALID:
                missing_items.append("Stock Repurchases")
            return MetricResult(
                metric_id=FundamentalMetricId.SHAREHOLDER_YIELD,
                category=MetricCategory.CASH_FLOW,
                status=MetricStatus.UNAVAILABLE,
                value=None,
                unit=Unit.PERCENT,
                currency=None,
                period=period,
                diagnostics=[
                    MetricDiagnostic(
                        code=DiagnosticCode.MISSING_REQUIRED_FACT,
                        message=f"Missing required distribution component(s) for Shareholder Yield: {', '.join(missing_items)}.",
                        details={
                            "missing": ", ".join(missing_items),
                            "period": period.period_key,
                        },
                    )
                ],
                provenance=MetricProvenance(
                    formula_id="FORMULA_SHAREHOLDER_YIELD_GROSS_V1",
                    methodology_version=cls.METHODOLOGY_VERSION,
                    source_concepts=[
                        "Cash Dividends Paid",
                        "Repurchase Of Capital Stock",
                    ],
                    source_periods=[period.period_key],
                ),
            )

        if market_cap is None:
            return MetricResult(
                metric_id=FundamentalMetricId.SHAREHOLDER_YIELD,
                category=MetricCategory.CASH_FLOW,
                status=MetricStatus.UNAVAILABLE,
                value=None,
                unit=Unit.PERCENT,
                currency=None,
                period=period,
                diagnostics=[
                    MetricDiagnostic(
                        code=DiagnosticCode.MARKET_CAP_UNAVAILABLE,
                        message="Market capitalization is unavailable for Shareholder Yield computation.",
                        details={"period": period.period_key},
                    )
                ],
                provenance=MetricProvenance(
                    formula_id="FORMULA_SHAREHOLDER_YIELD_GROSS_V1",
                    methodology_version=cls.METHODOLOGY_VERSION,
                    source_fact_ids=div_res.provenance.source_fact_ids
                    + rep_res.provenance.source_fact_ids,
                    source_concepts=[
                        "Cash Dividends Paid",
                        "Repurchase Of Capital Stock",
                    ],
                    source_periods=[period.period_key],
                ),
            )

        if market_cap <= 0:
            return MetricResult(
                metric_id=FundamentalMetricId.SHAREHOLDER_YIELD,
                category=MetricCategory.CASH_FLOW,
                status=MetricStatus.DISTORTED,
                value=None,
                unit=Unit.PERCENT,
                currency=None,
                period=period,
                diagnostics=[
                    MetricDiagnostic(
                        code=DiagnosticCode.NON_POSITIVE_MARKET_CAP,
                        message=f"Market capitalization must be strictly positive, got {market_cap}.",
                        details={
                            "market_cap": str(market_cap),
                            "period": period.period_key,
                        },
                    )
                ],
                provenance=MetricProvenance(
                    formula_id="FORMULA_SHAREHOLDER_YIELD_GROSS_V1",
                    methodology_version=cls.METHODOLOGY_VERSION,
                    source_fact_ids=div_res.provenance.source_fact_ids
                    + rep_res.provenance.source_fact_ids,
                    source_concepts=[
                        "Cash Dividends Paid",
                        "Repurchase Of Capital Stock",
                    ],
                    source_periods=[period.period_key],
                ),
            )

        total_dist = div_res.value + rep_res.value
        yield_val = total_dist / market_cap
        return MetricResult(
            metric_id=FundamentalMetricId.SHAREHOLDER_YIELD,
            category=MetricCategory.CASH_FLOW,
            status=MetricStatus.VALID,
            value=yield_val,
            unit=Unit.PERCENT,
            currency=None,
            period=period,
            diagnostics=[],
            provenance=MetricProvenance(
                formula_id="FORMULA_SHAREHOLDER_YIELD_GROSS_V1",
                methodology_version=cls.METHODOLOGY_VERSION,
                source_fact_ids=div_res.provenance.source_fact_ids
                + rep_res.provenance.source_fact_ids,
                source_concepts=["Cash Dividends Paid", "Repurchase Of Capital Stock"],
                source_periods=[period.period_key],
                methodology_notes=(
                    f"Shareholder Yield = (Dividends {div_res.value} + Repurchases {rep_res.value}) "
                    f"/ Market Cap {market_cap} = {yield_val}."
                ),
            ),
        )

    @classmethod
    def calculate_net_shareholder_yield(
        cls,
        period: FinancialPeriod,
        fact_store: MultiPeriodFactStore,
        market_cap: Decimal | None,
    ) -> MetricResult:
        """
        Calculate Net Shareholder Yield (dilution-adjusted):
          (Dividends Paid + Stock Repurchases - Stock Issuances) / Market Cap.
        """
        div_res = cls.calculate_dividends_paid(period, fact_store)
        rep_res = cls.calculate_stock_repurchases(period, fact_store)
        iss_res = cls.calculate_stock_issuances(period, fact_store)

        if (
            div_res.status != MetricStatus.VALID
            or rep_res.status != MetricStatus.VALID
            or iss_res.status != MetricStatus.VALID
            or div_res.value is None
            or rep_res.value is None
            or iss_res.value is None
        ):
            missing_items = []
            if div_res.status != MetricStatus.VALID:
                missing_items.append("Dividends Paid")
            if rep_res.status != MetricStatus.VALID:
                missing_items.append("Stock Repurchases")
            if iss_res.status != MetricStatus.VALID:
                missing_items.append("Stock Issuances")
            return MetricResult(
                metric_id=FundamentalMetricId.NET_SHAREHOLDER_YIELD,
                category=MetricCategory.CASH_FLOW,
                status=MetricStatus.UNAVAILABLE,
                value=None,
                unit=Unit.PERCENT,
                currency=None,
                period=period,
                diagnostics=[
                    MetricDiagnostic(
                        code=DiagnosticCode.MISSING_REQUIRED_FACT,
                        message=f"Missing distribution/issuance component(s) for Net Shareholder Yield: {', '.join(missing_items)}.",
                        details={
                            "missing": ", ".join(missing_items),
                            "period": period.period_key,
                        },
                    )
                ],
                provenance=MetricProvenance(
                    formula_id="FORMULA_NET_SHAREHOLDER_YIELD_DILUTION_ADJUSTED_V1",
                    methodology_version=cls.METHODOLOGY_VERSION,
                    source_concepts=[
                        "Cash Dividends Paid",
                        "Repurchase Of Capital Stock",
                        "Issuance Of Capital Stock",
                    ],
                    source_periods=[period.period_key],
                ),
            )

        if market_cap is None:
            return MetricResult(
                metric_id=FundamentalMetricId.NET_SHAREHOLDER_YIELD,
                category=MetricCategory.CASH_FLOW,
                status=MetricStatus.UNAVAILABLE,
                value=None,
                unit=Unit.PERCENT,
                currency=None,
                period=period,
                diagnostics=[
                    MetricDiagnostic(
                        code=DiagnosticCode.MARKET_CAP_UNAVAILABLE,
                        message="Market capitalization is unavailable for Net Shareholder Yield.",
                        details={"period": period.period_key},
                    )
                ],
                provenance=MetricProvenance(
                    formula_id="FORMULA_NET_SHAREHOLDER_YIELD_DILUTION_ADJUSTED_V1",
                    methodology_version=cls.METHODOLOGY_VERSION,
                    source_fact_ids=div_res.provenance.source_fact_ids
                    + rep_res.provenance.source_fact_ids
                    + iss_res.provenance.source_fact_ids,
                    source_concepts=[
                        "Cash Dividends Paid",
                        "Repurchase Of Capital Stock",
                        "Issuance Of Capital Stock",
                    ],
                    source_periods=[period.period_key],
                ),
            )

        if market_cap <= 0:
            return MetricResult(
                metric_id=FundamentalMetricId.NET_SHAREHOLDER_YIELD,
                category=MetricCategory.CASH_FLOW,
                status=MetricStatus.DISTORTED,
                value=None,
                unit=Unit.PERCENT,
                currency=None,
                period=period,
                diagnostics=[
                    MetricDiagnostic(
                        code=DiagnosticCode.NON_POSITIVE_MARKET_CAP,
                        message=f"Market capitalization must be strictly positive, got {market_cap}.",
                        details={
                            "market_cap": str(market_cap),
                            "period": period.period_key,
                        },
                    )
                ],
                provenance=MetricProvenance(
                    formula_id="FORMULA_NET_SHAREHOLDER_YIELD_DILUTION_ADJUSTED_V1",
                    methodology_version=cls.METHODOLOGY_VERSION,
                    source_fact_ids=div_res.provenance.source_fact_ids
                    + rep_res.provenance.source_fact_ids
                    + iss_res.provenance.source_fact_ids,
                    source_concepts=[
                        "Cash Dividends Paid",
                        "Repurchase Of Capital Stock",
                        "Issuance Of Capital Stock",
                    ],
                    source_periods=[period.period_key],
                ),
            )

        net_dist = div_res.value + rep_res.value - iss_res.value
        yield_val = net_dist / market_cap
        return MetricResult(
            metric_id=FundamentalMetricId.NET_SHAREHOLDER_YIELD,
            category=MetricCategory.CASH_FLOW,
            status=MetricStatus.VALID,
            value=yield_val,
            unit=Unit.PERCENT,
            currency=None,
            period=period,
            diagnostics=[],
            provenance=MetricProvenance(
                formula_id="FORMULA_NET_SHAREHOLDER_YIELD_DILUTION_ADJUSTED_V1",
                methodology_version=cls.METHODOLOGY_VERSION,
                source_fact_ids=div_res.provenance.source_fact_ids
                + rep_res.provenance.source_fact_ids
                + iss_res.provenance.source_fact_ids,
                source_concepts=[
                    "Cash Dividends Paid",
                    "Repurchase Of Capital Stock",
                    "Issuance Of Capital Stock",
                ],
                source_periods=[period.period_key],
                methodology_notes=(
                    f"Net Shareholder Yield = (Dividends {div_res.value} + Buybacks {rep_res.value} - Issuances {iss_res.value}) "
                    f"/ Market Cap {market_cap} = {yield_val}."
                ),
            ),
        )

    # -------------------------------------------------------------------------
    # Helper
    # -------------------------------------------------------------------------

    @classmethod
    def _compute_yield(
        cls,
        metric_id: FundamentalMetricId,
        period: FinancialPeriod,
        numerator_res: MetricResult,
        market_cap: Decimal | None,
        formula_id: str,
        notes: str,
    ) -> MetricResult:
        if numerator_res.status != MetricStatus.VALID or numerator_res.value is None:
            return MetricResult(
                metric_id=metric_id,
                category=MetricCategory.CASH_FLOW,
                status=numerator_res.status,
                value=None,
                unit=Unit.PERCENT,
                currency=None,
                period=period,
                diagnostics=numerator_res.diagnostics,
                provenance=MetricProvenance(
                    formula_id=formula_id,
                    methodology_version=cls.METHODOLOGY_VERSION,
                    source_concepts=numerator_res.provenance.source_concepts,
                    source_periods=[period.period_key],
                    methodology_notes="Numerator unavailable for yield computation.",
                ),
            )

        if market_cap is None:
            return MetricResult(
                metric_id=metric_id,
                category=MetricCategory.CASH_FLOW,
                status=MetricStatus.UNAVAILABLE,
                value=None,
                unit=Unit.PERCENT,
                currency=None,
                period=period,
                diagnostics=[
                    MetricDiagnostic(
                        code=DiagnosticCode.MARKET_CAP_UNAVAILABLE,
                        message="Market capitalization is unavailable for yield computation.",
                        details={"period": period.period_key},
                    )
                ],
                provenance=MetricProvenance(
                    formula_id=formula_id,
                    methodology_version=cls.METHODOLOGY_VERSION,
                    source_fact_ids=numerator_res.provenance.source_fact_ids,
                    source_concepts=numerator_res.provenance.source_concepts,
                    source_periods=[period.period_key],
                ),
            )

        if market_cap <= 0:
            return MetricResult(
                metric_id=metric_id,
                category=MetricCategory.CASH_FLOW,
                status=MetricStatus.DISTORTED,
                value=None,
                unit=Unit.PERCENT,
                currency=None,
                period=period,
                diagnostics=[
                    MetricDiagnostic(
                        code=DiagnosticCode.NON_POSITIVE_MARKET_CAP,
                        message=f"Market capitalization must be strictly positive, got {market_cap}.",
                        details={
                            "market_cap": str(market_cap),
                            "period": period.period_key,
                        },
                    )
                ],
                provenance=MetricProvenance(
                    formula_id=formula_id,
                    methodology_version=cls.METHODOLOGY_VERSION,
                    source_fact_ids=numerator_res.provenance.source_fact_ids,
                    source_concepts=numerator_res.provenance.source_concepts,
                    source_periods=[period.period_key],
                ),
            )

        val = numerator_res.value / market_cap
        return MetricResult(
            metric_id=metric_id,
            category=MetricCategory.CASH_FLOW,
            status=MetricStatus.VALID,
            value=val,
            unit=Unit.PERCENT,
            currency=None,
            period=period,
            diagnostics=[],
            provenance=MetricProvenance(
                formula_id=formula_id,
                methodology_version=cls.METHODOLOGY_VERSION,
                source_fact_ids=numerator_res.provenance.source_fact_ids,
                source_concepts=numerator_res.provenance.source_concepts,
                source_periods=[period.period_key],
                methodology_notes=f"{notes} ({numerator_res.value} / {market_cap} = {val}).",
            ),
        )

    # Convenient canonical aliases
    calculate_cfo = calculate_operating_cash_flow
    calculate_capex = calculate_capital_expenditures
    calculate_stock_issuance = calculate_stock_issuances
    calculate_gross_shareholder_yield = calculate_shareholder_yield
