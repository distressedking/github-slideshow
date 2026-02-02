"""
TED Europa Scraper

A Python scraper for the Tenders Electronic Daily (TED) database.
"""

__version__ = "1.0.0"
__author__ = "TED Scraper"

from .scraper import TEDScraper, TEDSeleniumScraper, TEDScraperError
from .classifier import TenderClassifier, KeywordExtractor, CPVAnalyzer
from .models.tender import Tender, TenderCollection

__all__ = [
    'TEDScraper',
    'TEDSeleniumScraper',
    'TEDScraperError',
    'TenderClassifier',
    'KeywordExtractor',
    'CPVAnalyzer',
    'Tender',
    'TenderCollection',
]
