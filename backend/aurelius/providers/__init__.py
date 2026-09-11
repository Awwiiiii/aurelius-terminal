"""
aurelius.providers
==================
External data provider abstraction layer.

Design principle:
  AURELIUS must not be tightly coupled to any single data provider.
  All provider implementations satisfy the abstract interface defined here.
  The API layer receives a provider via dependency injection and never
  references a concrete provider class directly.

This module is the correct location for:
  - Abstract base classes (interfaces) for market data providers
  - Provider registry / factory
  - Provider-selection logic

Milestone 0: Module structure established. No providers implemented.
Milestone 1: Will introduce:
  - MarketDataProvider (abstract interface)
  - YahooFinanceProvider (first concrete implementation)
  - ProviderRegistry

Do not implement providers in Milestone 0.
"""
