# TED Europa Scraper

A Python scraper for the Tenders Electronic Daily (TED) database - the official source of European public procurement notices.

## Features

- **Search API integration** - Uses TED's underlying search API for efficient data retrieval
- **Configurable search parameters** - Text search, CPV codes, scope, date ranges
- **Automatic pagination** - Handles multi-page results automatically
- **Tender classification** - Rule-based classification of tenders by category
- **Multiple export formats** - JSON and CSV output
- **Analysis tools** - CPV distribution, keyword extraction, category statistics
- **Selenium fallback** - Browser automation for JavaScript-heavy content

## Installation

```bash
cd ted_scraper
pip install -r requirements.txt
```

For Selenium mode (optional):
```bash
pip install selenium webdriver-manager
```

## Quick Start

```bash
# Run with default settings (searches for "Airport" tenders)
python main.py

# Custom search text
python main.py --text "railway station"

# Specify CPV codes
python main.py --text "airport" --cpv 72000000,48000000,30200000

# Limit results
python main.py --max-results 100

# Export to specific format
python main.py --format csv --output ./my_results
```

## Configuration

Edit `config/search_config.py` to customize default search parameters:

```python
# Search text
SEARCH_TEXT = "Airport"

# Search scope: "ACTIVE", "LATEST", or "ALL"
SEARCH_SCOPE = "ACTIVE"

# CPV codes to filter by
CPV_CODES = {
    "72000000": {"description": "IT services", "selected": True},
    "48000000": {"description": "Software", "selected": True},
    # ...
}
```

## CPV Codes Reference

The scraper uses Common Procurement Vocabulary (CPV) codes to filter tenders. Key codes for IT/technology:

| Code | Description |
|------|-------------|
| 30000000 | Office and computing machinery |
| 30200000 | Computer equipment and supplies |
| 32000000 | Radio, television, communication equipment |
| 35000000 | Security, defence equipment |
| 48000000 | Software packages and information systems |
| 72000000 | IT services: consulting, development, support |

## Output Files

The scraper creates timestamped output folders containing:

- `tenders.json` - Full tender data in JSON format
- `tenders.csv` - Tender summary in CSV format
- `analysis.json` - Analysis results (categories, CPV distribution, keywords)

## Classification Categories

The classifier categorizes airport-related tenders into:

- `IT_INFRASTRUCTURE` - Servers, networks, data centers
- `SECURITY_SYSTEMS` - CCTV, access control, screening
- `SOFTWARE_DEVELOPMENT` - Custom software, applications
- `HARDWARE_EQUIPMENT` - Computers, terminals, printers
- `CONSULTING_SERVICES` - IT consulting, maintenance
- `COMMUNICATION_SYSTEMS` - Radio, telecom equipment
- `BAGGAGE_HANDLING` - Conveyor systems, sorting
- `PASSENGER_SYSTEMS` - Check-in, boarding, kiosks
- `FLIGHT_INFORMATION` - FIDS, display systems
- `GROUND_SUPPORT` - Ground handling equipment

## Python API Usage

```python
from scraper import TEDScraper
from classifier import TenderClassifier

# Initialize scraper
scraper = TEDScraper(
    search_text="airport",
    cpv_codes=["72000000", "48000000"],
    scope="ACTIVE",
    max_results=500
)

# Scrape tenders
collection = scraper.scrape()

# Classify results
classifier = TenderClassifier()
collection = classifier.classify_collection(collection)

# Export
collection.to_json("tenders.json")
collection.to_csv("tenders.csv")

# Analyze
print(collection.summary())
print(classifier.get_category_distribution(collection))
```

## Command Line Options

```
usage: main.py [-h] [-t TEXT] [-c CPV] [-s {ACTIVE,LATEST,ALL}]
               [-m MAX_RESULTS] [-p PAGE_SIZE] [-o OUTPUT]
               [-f {json,csv,both}] [--selenium] [--no-headless]
               [--no-classify] [--analyze-keywords] [-v] [-q]

Options:
  -t, --text          Search text (default: "Airport")
  -c, --cpv           Comma-separated CPV codes
  -s, --scope         Search scope: ACTIVE, LATEST, ALL
  -m, --max-results   Maximum results to fetch
  -p, --page-size     Results per page
  -o, --output        Output directory
  -f, --format        Output format: json, csv, both
  --selenium          Use browser automation
  --no-classify       Skip classification
  --analyze-keywords  Extract keywords from results
  -v, --verbose       Verbose logging
  -q, --quiet         Suppress output
```

## Legal Notice

This scraper is intended for legitimate research and business purposes. Please:

- Respect TED's terms of service
- Implement appropriate rate limiting
- Do not overload the service with excessive requests
- Credit TED Europa as the data source

TED data is published under the EU Open Data policy.

## License

MIT License
