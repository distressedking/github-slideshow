"""
Utility functions for the TED scraper.
"""

import logging
import time
from functools import wraps
from typing import Callable, Any


def setup_logging(level: int = logging.INFO) -> logging.Logger:
    """Set up logging configuration."""
    logging.basicConfig(
        level=level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    return logging.getLogger('ted_scraper')


def rate_limit(delay: float = 1.0) -> Callable:
    """Decorator to add rate limiting between function calls."""
    last_call = [0.0]

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs) -> Any:
            elapsed = time.time() - last_call[0]
            if elapsed < delay:
                time.sleep(delay - elapsed)
            result = func(*args, **kwargs)
            last_call[0] = time.time()
            return result
        return wrapper
    return decorator


def retry_on_failure(max_retries: int = 3, delay: float = 2.0) -> Callable:
    """Decorator to retry function on failure with exponential backoff."""
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs) -> Any:
            last_exception = None
            for attempt in range(max_retries):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    last_exception = e
                    if attempt < max_retries - 1:
                        wait_time = delay * (2 ** attempt)
                        logging.warning(
                            f"Attempt {attempt + 1} failed: {e}. "
                            f"Retrying in {wait_time}s..."
                        )
                        time.sleep(wait_time)
            raise last_exception
        return wrapper
    return decorator


def clean_text(text: str) -> str:
    """Clean and normalize text content."""
    if not text:
        return ""
    # Remove extra whitespace
    text = ' '.join(text.split())
    return text.strip()


def parse_money(value_str: str) -> tuple[float, str]:
    """Parse monetary value string into amount and currency."""
    if not value_str:
        return 0.0, "EUR"

    # Common currency patterns
    currencies = ['EUR', 'USD', 'GBP', 'CHF', 'SEK', 'DKK', 'NOK', 'PLN', 'CZK', 'HUF']

    currency = "EUR"
    for curr in currencies:
        if curr in value_str.upper():
            currency = curr
            break

    # Extract numeric value
    import re
    numbers = re.findall(r'[\d,]+\.?\d*', value_str.replace(',', ''))
    if numbers:
        try:
            amount = float(numbers[0].replace(',', ''))
            return amount, currency
        except ValueError:
            pass

    return 0.0, currency
