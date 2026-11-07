"""Test settings: pin the demo date, and never call paid external APIs (Firecrawl) from tests.

Set before any backend import; python-dotenv never overrides variables that are already set.
"""
import os

os.environ["HEIRLOOM_AS_OF"] = "2026-11-07"
os.environ["FIRECRAWL_API_KEY"] = ""
