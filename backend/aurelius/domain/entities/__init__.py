"""
aurelius.domain.entities
========================
Core financial domain entities for AURELIUS.

Entities are introduced incrementally — only when a milestone requires them.
This file documents what entities EXIST now vs. what is PLANNED for future milestones.

Milestone 0 — Created:
  (empty — no financial entities required yet; structure established)

Milestone 1 — Will introduce:
  Security   — Ticker, name, exchange, asset type, currency
  Price      — A single price observation with timestamp and source
  OHLCV      — Open/High/Low/Close/Volume bar for a single period
  Quote      — Real-time or delayed market quote snapshot

Milestone 4+ — Will introduce:
  PriceReturn, LogReturn, CumulativeReturn

Milestone 5+ — Will introduce:
  Volatility, Drawdown

Milestone 6+ — Will introduce:
  FinancialStatement (IncomeStatement, BalanceSheet, CashFlowStatement)

Do not create entities prematurely.
"""
