"""
aurelius — Financial Intelligence & Research Terminal

This is the top-level package. Sub-packages:
  aurelius.api          — FastAPI application layer
  aurelius.domain       — Pure financial domain (no I/O)
  aurelius.providers    — External data provider abstraction
  aurelius.infrastructure — I/O adapters (HTTP, logging, database in later milestones)
"""

__version__ = "0.1.0"
