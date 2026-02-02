#!/usr/bin/env python3
"""
TED Europa Scraper - Main Entry Point

A scraper for the Tenders Electronic Daily (TED) database,
the official source of European public procurement notices.

Usage:
    python main.py                    # Run with default settings
    python main.py --text "airport"   # Custom search text
    python main.py --output results   # Custom output directory
    python main.py --max-results 100  # Limit results
"""

import argparse
import json
import os
import sys
from datetime import datetime
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from scraper import TEDScraper, TEDSeleniumScraper, TEDScraperError
from classifier import TenderClassifier, KeywordExtractor, CPVAnalyzer
from models.tender import TenderCollection
from config.search_config import (
    SEARCH_TEXT, SEARCH_SCOPE, get_selected_cpv_codes,
    DEFAULT_PAGE_SIZE, MAX_RESULTS
)
from utils.helpers import setup_logging


def parse_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description='Scrape tender notices from TED Europa',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    %(prog)s --text "airport security"
    %(prog)s --text "airport" --cpv 72000000,48000000
    %(prog)s --output ./airport_tenders --format csv
    %(prog)s --selenium  # Use browser automation
        """
    )

    # Search parameters
    parser.add_argument(
        '-t', '--text',
        default=SEARCH_TEXT,
        help=f'Search text (default: "{SEARCH_TEXT}")'
    )
    parser.add_argument(
        '-c', '--cpv',
        help='Comma-separated CPV codes (default: from config)'
    )
    parser.add_argument(
        '-s', '--scope',
        choices=['ACTIVE', 'LATEST', 'ALL'],
        default=SEARCH_SCOPE,
        help=f'Search scope (default: {SEARCH_SCOPE})'
    )

    # Result limits
    parser.add_argument(
        '-m', '--max-results',
        type=int,
        default=MAX_RESULTS,
        help=f'Maximum results to fetch (default: {MAX_RESULTS})'
    )
    parser.add_argument(
        '-p', '--page-size',
        type=int,
        default=DEFAULT_PAGE_SIZE,
        help=f'Results per page (default: {DEFAULT_PAGE_SIZE})'
    )

    # Output options
    parser.add_argument(
        '-o', '--output',
        default='./output',
        help='Output directory (default: ./output)'
    )
    parser.add_argument(
        '-f', '--format',
        choices=['json', 'csv', 'both'],
        default='both',
        help='Output format (default: both)'
    )

    # Scraper mode
    parser.add_argument(
        '--selenium',
        action='store_true',
        help='Use Selenium browser automation (slower but more reliable)'
    )
    parser.add_argument(
        '--no-headless',
        action='store_true',
        help='Show browser window (only with --selenium)'
    )

    # Classification
    parser.add_argument(
        '--no-classify',
        action='store_true',
        help='Skip classification step'
    )
    parser.add_argument(
        '--analyze-keywords',
        action='store_true',
        help='Extract and analyze keywords from results'
    )

    # Verbosity
    parser.add_argument(
        '-v', '--verbose',
        action='store_true',
        help='Enable verbose logging'
    )
    parser.add_argument(
        '-q', '--quiet',
        action='store_true',
        help='Suppress output except errors'
    )

    return parser.parse_args()


def create_output_directory(output_path: str) -> Path:
    """Create output directory with timestamp subfolder."""
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    output_dir = Path(output_path) / timestamp
    output_dir.mkdir(parents=True, exist_ok=True)
    return output_dir


def save_results(
    collection: TenderCollection,
    output_dir: Path,
    format: str,
    logger
) -> dict:
    """Save results to files."""
    saved_files = {}

    if format in ('json', 'both'):
        json_path = output_dir / 'tenders.json'
        collection.to_json(str(json_path))
        saved_files['json'] = str(json_path)
        logger.info(f"Saved JSON: {json_path}")

    if format in ('csv', 'both'):
        csv_path = output_dir / 'tenders.csv'
        collection.to_csv(str(csv_path))
        saved_files['csv'] = str(csv_path)
        logger.info(f"Saved CSV: {csv_path}")

    return saved_files


def save_analysis(
    collection: TenderCollection,
    classifier: TenderClassifier,
    output_dir: Path,
    analyze_keywords: bool,
    logger
):
    """Save analysis results."""
    analysis = {
        'summary': collection.summary(),
        'category_distribution': classifier.get_category_distribution(collection),
        'search_query': collection.search_query,
        'search_date': collection.search_date.isoformat() if collection.search_date else None,
        'total_results': len(collection)
    }

    # CPV analysis
    cpv_analyzer = CPVAnalyzer()
    analysis['cpv_analysis'] = cpv_analyzer.analyze(collection)

    # Keyword analysis (optional)
    if analyze_keywords:
        keyword_extractor = KeywordExtractor()
        analysis['top_keywords'] = keyword_extractor.extract_keywords(collection)
        analysis['top_bigrams'] = keyword_extractor.extract_bigrams(collection)

    # Save analysis
    analysis_path = output_dir / 'analysis.json'
    with open(analysis_path, 'w', encoding='utf-8') as f:
        json.dump(analysis, f, indent=2, ensure_ascii=False)
    logger.info(f"Saved analysis: {analysis_path}")

    return analysis


def print_summary(collection: TenderCollection, analysis: dict):
    """Print summary to console."""
    print("\n" + "=" * 60)
    print("SCRAPING COMPLETE")
    print("=" * 60)

    print(f"\nTotal tenders scraped: {len(collection)}")
    print(f"Search query: {collection.search_query}")

    if 'category_distribution' in analysis:
        print("\nCategory Distribution:")
        for category, count in sorted(
            analysis['category_distribution'].items(),
            key=lambda x: x[1],
            reverse=True
        ):
            print(f"  {category}: {count}")

    if 'cpv_analysis' in analysis:
        cpv = analysis['cpv_analysis']
        print(f"\nCPV Analysis:")
        print(f"  Unique CPV divisions: {cpv['total_unique_divisions']}")
        print(f"  Unique CPV codes: {cpv['total_unique_codes']}")
        print("\n  Top divisions:")
        for div, count in list(cpv['division_distribution'].items())[:5]:
            print(f"    {div}: {count}")

    if 'top_keywords' in analysis and analysis['top_keywords']:
        print("\nTop Keywords:")
        for keyword, freq in analysis['top_keywords'][:10]:
            print(f"  {keyword}: {freq}")

    print("\n" + "=" * 60)


def main():
    """Main entry point."""
    args = parse_args()

    # Setup logging
    import logging
    if args.quiet:
        log_level = logging.ERROR
    elif args.verbose:
        log_level = logging.DEBUG
    else:
        log_level = logging.INFO

    logger = setup_logging(log_level)

    # Parse CPV codes
    cpv_codes = None
    if args.cpv:
        cpv_codes = [c.strip() for c in args.cpv.split(',')]
    else:
        cpv_codes = get_selected_cpv_codes()

    # Create output directory
    output_dir = create_output_directory(args.output)
    logger.info(f"Output directory: {output_dir}")

    # Initialize scraper
    try:
        if args.selenium:
            logger.info("Using Selenium scraper")
            scraper = TEDSeleniumScraper(
                search_text=args.text,
                cpv_codes=cpv_codes,
                scope=args.scope,
                page_size=args.page_size,
                max_results=args.max_results,
                headless=not args.no_headless
            )
        else:
            logger.info("Using API scraper")
            scraper = TEDScraper(
                search_text=args.text,
                cpv_codes=cpv_codes,
                scope=args.scope,
                page_size=args.page_size,
                max_results=args.max_results
            )

        # Run scraper
        logger.info("Starting scrape...")
        collection = scraper.scrape()

        if not collection.tenders:
            logger.warning("No results found!")
            print("\nNo tenders found matching your search criteria.")
            return 1

        logger.info(f"Scraped {len(collection)} tenders")

        # Classify results
        classifier = TenderClassifier()
        if not args.no_classify:
            logger.info("Classifying tenders...")
            collection = classifier.classify_collection(collection)

        # Save results
        save_results(collection, output_dir, args.format, logger)

        # Save and print analysis
        analysis = save_analysis(
            collection,
            classifier,
            output_dir,
            args.analyze_keywords,
            logger
        )

        if not args.quiet:
            print_summary(collection, analysis)

        print(f"\nResults saved to: {output_dir}")
        return 0

    except TEDScraperError as e:
        logger.error(f"Scraper error: {e}")
        print(f"\nError: {e}")
        return 1
    except KeyboardInterrupt:
        logger.info("Interrupted by user")
        print("\nInterrupted by user")
        return 130
    except Exception as e:
        logger.exception(f"Unexpected error: {e}")
        print(f"\nUnexpected error: {e}")
        return 1


if __name__ == '__main__':
    sys.exit(main())
