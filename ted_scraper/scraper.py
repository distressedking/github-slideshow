"""
TED Europa Scraper - Main scraping module.

This scraper supports two modes:
1. API mode (recommended) - Uses TED's underlying search API
2. Browser mode - Uses Selenium for JavaScript-rendered content

The TED website uses a Liferay/React frontend, so the API approach
is more reliable and efficient.
"""

import json
import logging
import time
import re
from datetime import datetime
from typing import Optional, Dict, List, Any, Generator
from urllib.parse import urljoin, urlencode

import requests
from bs4 import BeautifulSoup

from models.tender import Tender, TenderCollection
from config.search_config import (
    SEARCH_TEXT, SEARCH_SCOPE, TED_BASE_URL,
    get_selected_cpv_codes, DEFAULT_PAGE_SIZE, MAX_RESULTS,
    REQUEST_DELAY, MAX_RETRIES, RETRY_DELAY
)
from utils.helpers import setup_logging, clean_text, retry_on_failure


class TEDScraperError(Exception):
    """Custom exception for TED scraper errors."""
    pass


class TEDScraper:
    """
    Scraper for TED Europa (Tenders Electronic Daily).

    This class provides methods to search and extract tender notices
    from the European Union's public procurement database.
    """

    # TED API endpoints (discovered through network analysis)
    SEARCH_API_URL = "https://ted.europa.eu/api/v3.0/notices/search"
    NOTICE_API_URL = "https://ted.europa.eu/api/v3.0/notices"

    # Alternative search endpoint (web interface)
    WEB_SEARCH_URL = "https://ted.europa.eu/en/search/result"

    def __init__(
        self,
        search_text: str = SEARCH_TEXT,
        cpv_codes: Optional[List[str]] = None,
        scope: str = SEARCH_SCOPE,
        page_size: int = DEFAULT_PAGE_SIZE,
        max_results: int = MAX_RESULTS
    ):
        """
        Initialize the TED scraper.

        Args:
            search_text: Text to search for in tender notices
            cpv_codes: List of CPV codes to filter by
            scope: Search scope ('ACTIVE', 'LATEST', 'ALL')
            page_size: Number of results per page
            max_results: Maximum total results to fetch
        """
        self.search_text = search_text
        self.cpv_codes = cpv_codes or get_selected_cpv_codes()
        self.scope = scope
        self.page_size = page_size
        self.max_results = max_results

        self.logger = setup_logging()
        self.session = self._create_session()

        self.logger.info(f"TED Scraper initialized")
        self.logger.info(f"Search text: {self.search_text}")
        self.logger.info(f"CPV codes: {self.cpv_codes}")
        self.logger.info(f"Scope: {self.scope}")

    def _create_session(self) -> requests.Session:
        """Create a requests session with appropriate headers."""
        session = requests.Session()
        session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'application/json, text/plain, */*',
            'Accept-Language': 'en-US,en;q=0.9',
            'Accept-Encoding': 'gzip, deflate, br',
            'Origin': 'https://ted.europa.eu',
            'Referer': 'https://ted.europa.eu/en/search/result',
        })
        return session

    def _build_search_query(self) -> str:
        """
        Build the TED query string using their query syntax.

        TED uses a specific query language for searches.
        Documentation: https://ted.europa.eu/en/help#h2-expert-search
        """
        query_parts = []

        # Add full-text search
        if self.search_text:
            query_parts.append(f'FT="{self.search_text}"')

        # Add CPV code filters
        if self.cpv_codes:
            cpv_query = ' OR '.join([f'cpv.code={code}*' for code in self.cpv_codes])
            query_parts.append(f'({cpv_query})')

        return ' AND '.join(query_parts) if query_parts else '*'

    def _build_api_payload(self, page: int = 1) -> Dict[str, Any]:
        """Build the API request payload for search."""
        return {
            "query": self._build_search_query(),
            "scope": self.scope,
            "page": page,
            "pageSize": self.page_size,
            "sortField": "PUBLICATION_DATE",
            "sortOrder": "DESC",
            "fields": [
                "ND",  # Notice Document number
                "TI",  # Title
                "CY",  # Country
                "TW",  # Town
                "AA",  # Awarding Authority
                "DD",  # Document Deadline Date
                "DT",  # Document Type
                "NC",  # Notice Type Code
                "PR",  # Procedure Type
                "RP",  # Reference Publication
                "TD",  # Document Type Description
                "PD",  # Publication Date
                "OC",  # Original CPV
                "AC",  # Additional CPV
                "MA",  # Main Activity
                "TY",  # Type of Buyer
            ]
        }

    def search_api(self, page: int = 1) -> Dict[str, Any]:
        """
        Perform search using TED's API.

        Args:
            page: Page number to fetch

        Returns:
            API response as dictionary
        """
        payload = self._build_api_payload(page)

        self.logger.debug(f"Searching page {page} with payload: {json.dumps(payload, indent=2)}")

        try:
            response = self.session.post(
                self.SEARCH_API_URL,
                json=payload,
                timeout=30
            )
            response.raise_for_status()
            return response.json()
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 403:
                self.logger.warning("API access forbidden, falling back to web scraping")
                return self._search_web_fallback(page)
            raise TEDScraperError(f"API request failed: {e}")
        except requests.exceptions.RequestException as e:
            raise TEDScraperError(f"Network error: {e}")

    def _search_web_fallback(self, page: int = 1) -> Dict[str, Any]:
        """
        Fallback method using web scraping when API is not accessible.

        This parses the HTML search results page.
        """
        params = {
            'FT': self.search_text,
            'scope': self.scope,
            'page': page,
            'pageSize': self.page_size,
        }

        # Add CPV codes
        if self.cpv_codes:
            params['cpv'] = ','.join(self.cpv_codes)

        url = f"{self.WEB_SEARCH_URL}?{urlencode(params)}"

        try:
            response = self.session.get(url, timeout=30)
            response.raise_for_status()

            # Parse the response - TED uses React, so we need to find
            # the embedded JSON data
            soup = BeautifulSoup(response.text, 'html.parser')

            # Look for embedded JSON data in script tags
            scripts = soup.find_all('script')
            for script in scripts:
                if script.string and 'searchResults' in script.string:
                    # Extract JSON from script
                    match = re.search(r'window\.__INITIAL_STATE__\s*=\s*({.*?});', script.string, re.DOTALL)
                    if match:
                        return json.loads(match.group(1))

            # If no embedded data, parse HTML
            return self._parse_html_results(soup)

        except Exception as e:
            self.logger.error(f"Web fallback failed: {e}")
            raise TEDScraperError(f"Web scraping failed: {e}")

    def _parse_html_results(self, soup: BeautifulSoup) -> Dict[str, Any]:
        """Parse HTML search results into structured data."""
        results = []

        # Find result items (adjust selectors based on actual HTML structure)
        items = soup.select('.search-result-item, .notice-item, [data-notice-id]')

        for item in items:
            try:
                notice = {
                    'id': item.get('data-notice-id', ''),
                    'title': clean_text(item.select_one('.title, h3, h4')?.get_text() or ''),
                    'buyer': clean_text(item.select_one('.buyer, .authority')?.get_text() or ''),
                    'country': clean_text(item.select_one('.country, [data-country]')?.get_text() or ''),
                    'date': clean_text(item.select_one('.date, time')?.get_text() or ''),
                    'url': item.select_one('a')?.get('href', ''),
                }
                if notice['id'] or notice['title']:
                    results.append(notice)
            except Exception as e:
                self.logger.warning(f"Failed to parse result item: {e}")
                continue

        # Extract pagination info
        total_elem = soup.select_one('.total-results, .result-count')
        total = 0
        if total_elem:
            match = re.search(r'(\d+)', total_elem.get_text())
            if match:
                total = int(match.group(1))

        return {
            'results': results,
            'total': total or len(results),
            'page': 1,
            'pageSize': self.page_size
        }

    def _parse_notice(self, raw_data: Dict[str, Any]) -> Tender:
        """Parse raw notice data into Tender object."""
        def safe_get(d, *keys, default=''):
            """Safely get nested dictionary values."""
            for key in keys:
                if isinstance(d, dict):
                    d = d.get(key, default)
                else:
                    return default
            return d if d else default

        # Extract CPV codes
        cpv_codes = []
        cpv_descriptions = []
        if 'OC' in raw_data:
            oc = raw_data['OC']
            if isinstance(oc, list):
                for item in oc:
                    if isinstance(item, dict):
                        cpv_codes.append(item.get('code', ''))
                        cpv_descriptions.append(item.get('description', ''))
                    else:
                        cpv_codes.append(str(item))
            elif isinstance(oc, str):
                cpv_codes.append(oc)

        # Parse dates
        pub_date = None
        if raw_data.get('PD'):
            try:
                pub_date = datetime.strptime(raw_data['PD'], '%Y-%m-%d')
            except (ValueError, TypeError):
                try:
                    pub_date = datetime.strptime(raw_data['PD'], '%Y%m%d')
                except (ValueError, TypeError):
                    pass

        deadline = None
        if raw_data.get('DD'):
            try:
                deadline = datetime.strptime(raw_data['DD'], '%Y-%m-%d')
            except (ValueError, TypeError):
                try:
                    deadline = datetime.strptime(raw_data['DD'], '%Y%m%d')
                except (ValueError, TypeError):
                    pass

        # Build notice URL
        notice_id = raw_data.get('ND', raw_data.get('id', ''))
        notice_url = f"{TED_BASE_URL}/en/notice/-/detail/{notice_id}" if notice_id else ''

        return Tender(
            notice_id=notice_id,
            publication_number=raw_data.get('RP', ''),
            title=clean_text(safe_get(raw_data, 'TI', default=raw_data.get('title', ''))),
            description=clean_text(raw_data.get('description', '')),
            publication_date=pub_date,
            submission_deadline=deadline,
            cpv_codes=cpv_codes,
            cpv_descriptions=cpv_descriptions,
            notice_type=safe_get(raw_data, 'TD', default=raw_data.get('type', '')),
            procedure_type=raw_data.get('PR', ''),
            buyer_name=clean_text(safe_get(raw_data, 'AA', default=raw_data.get('buyer', ''))),
            buyer_country=raw_data.get('CY', raw_data.get('country', '')),
            buyer_city=raw_data.get('TW', ''),
            notice_url=notice_url,
            raw_data=raw_data
        )

    def fetch_all_results(self) -> Generator[Tender, None, None]:
        """
        Fetch all search results with pagination.

        Yields:
            Tender objects as they are fetched
        """
        page = 1
        total_fetched = 0
        total_available = None

        while total_fetched < self.max_results:
            self.logger.info(f"Fetching page {page}...")

            try:
                response = self.search_api(page)
            except TEDScraperError as e:
                self.logger.error(f"Failed to fetch page {page}: {e}")
                break

            results = response.get('results', response.get('notices', []))
            total = response.get('total', response.get('totalCount', 0))

            if total_available is None:
                total_available = total
                self.logger.info(f"Total results available: {total_available}")

            if not results:
                self.logger.info("No more results to fetch")
                break

            for item in results:
                if total_fetched >= self.max_results:
                    break
                tender = self._parse_notice(item)
                yield tender
                total_fetched += 1

            self.logger.info(f"Fetched {total_fetched}/{min(total_available, self.max_results)} results")

            if total_fetched >= total_available:
                break

            page += 1
            time.sleep(REQUEST_DELAY)  # Rate limiting

    def scrape(self) -> TenderCollection:
        """
        Main scraping method - fetches all results and returns a collection.

        Returns:
            TenderCollection with all scraped tenders
        """
        self.logger.info("Starting scrape...")
        collection = TenderCollection(
            search_query=self._build_search_query(),
            search_date=datetime.now()
        )

        for tender in self.fetch_all_results():
            collection.add(tender)

        collection.total_results = len(collection)
        self.logger.info(f"Scrape complete. Total tenders: {len(collection)}")

        return collection

    def get_notice_details(self, notice_id: str) -> Optional[Tender]:
        """
        Fetch detailed information for a specific notice.

        Args:
            notice_id: The TED notice ID

        Returns:
            Tender object with full details, or None if not found
        """
        url = f"{self.NOTICE_API_URL}/{notice_id}"

        try:
            response = self.session.get(url, timeout=30)
            response.raise_for_status()
            data = response.json()
            return self._parse_notice(data)
        except requests.exceptions.HTTPError:
            # Try web fallback
            return self._get_notice_web(notice_id)
        except Exception as e:
            self.logger.error(f"Failed to fetch notice {notice_id}: {e}")
            return None

    def _get_notice_web(self, notice_id: str) -> Optional[Tender]:
        """Fetch notice details via web scraping."""
        url = f"{TED_BASE_URL}/en/notice/-/detail/{notice_id}"

        try:
            response = self.session.get(url, timeout=30)
            response.raise_for_status()

            soup = BeautifulSoup(response.text, 'html.parser')

            # Extract data from HTML (adjust selectors as needed)
            title = soup.select_one('h1, .notice-title')
            buyer = soup.select_one('.buyer-name, .contracting-authority')
            description = soup.select_one('.notice-description, .object-description')

            return Tender(
                notice_id=notice_id,
                title=clean_text(title.get_text() if title else ''),
                buyer_name=clean_text(buyer.get_text() if buyer else ''),
                description=clean_text(description.get_text() if description else ''),
                notice_url=url
            )
        except Exception as e:
            self.logger.error(f"Web fetch failed for notice {notice_id}: {e}")
            return None


class TEDSeleniumScraper(TEDScraper):
    """
    Selenium-based scraper for handling JavaScript-rendered content.

    Use this when the API and web scraping approaches fail due to
    heavy JavaScript rendering.
    """

    def __init__(self, *args, headless: bool = True, **kwargs):
        """
        Initialize Selenium scraper.

        Args:
            headless: Run browser in headless mode
            *args, **kwargs: Passed to parent TEDScraper
        """
        super().__init__(*args, **kwargs)
        self.headless = headless
        self.driver = None

    def _init_driver(self):
        """Initialize Selenium WebDriver."""
        try:
            from selenium import webdriver
            from selenium.webdriver.chrome.options import Options
            from selenium.webdriver.chrome.service import Service

            options = Options()
            if self.headless:
                options.add_argument('--headless')
            options.add_argument('--no-sandbox')
            options.add_argument('--disable-dev-shm-usage')
            options.add_argument('--disable-gpu')
            options.add_argument('--window-size=1920,1080')

            self.driver = webdriver.Chrome(options=options)
            self.logger.info("Selenium WebDriver initialized")
        except ImportError:
            raise TEDScraperError("Selenium not installed. Run: pip install selenium")
        except Exception as e:
            raise TEDScraperError(f"Failed to initialize WebDriver: {e}")

    def _close_driver(self):
        """Close Selenium WebDriver."""
        if self.driver:
            self.driver.quit()
            self.driver = None

    def search_selenium(self, page: int = 1) -> List[Dict[str, Any]]:
        """
        Perform search using Selenium.

        This method navigates to the search page, fills in the form,
        and extracts results from the rendered page.
        """
        from selenium.webdriver.common.by import By
        from selenium.webdriver.support.ui import WebDriverWait
        from selenium.webdriver.support import expected_conditions as EC

        if not self.driver:
            self._init_driver()

        # Build search URL with parameters
        params = {
            'FT': self.search_text,
            'scope': self.scope,
            'page': page,
        }
        url = f"{self.WEB_SEARCH_URL}?{urlencode(params)}"

        self.driver.get(url)

        # Wait for results to load
        try:
            WebDriverWait(self.driver, 20).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, '.search-results, .notice-list, [data-testid="search-results"]'))
            )
        except Exception:
            self.logger.warning("Timeout waiting for results")

        # Extract results
        results = []
        items = self.driver.find_elements(By.CSS_SELECTOR, '.search-result-item, .notice-item, [data-notice-id]')

        for item in items:
            try:
                notice = {
                    'id': item.get_attribute('data-notice-id') or '',
                    'title': item.find_element(By.CSS_SELECTOR, '.title, h3, h4').text,
                    'buyer': item.find_element(By.CSS_SELECTOR, '.buyer, .authority').text,
                    'url': item.find_element(By.TAG_NAME, 'a').get_attribute('href'),
                }
                results.append(notice)
            except Exception:
                continue

        return results

    def __enter__(self):
        """Context manager entry."""
        self._init_driver()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self._close_driver()
