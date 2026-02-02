"""
Search configuration for TED Europa scraper.
Based on the advanced search parameters from the UI.
"""

# Search text parameter
SEARCH_TEXT = "Airport"

# Search scope options
SEARCH_SCOPE = "ACTIVE"  # Options: "LATEST", "ACTIVE", "ALL"

# CPV (Common Procurement Vocabulary) codes for Business Sector
# Based on the image configuration
CPV_CODES = {
    # Office and computing machinery, equipment and supplies
    "30000000": {
        "description": "Office and computing machinery, equipment and supplies except furniture and software packages",
        "selected": True,
        "subcodes": {
            "30200000": {
                "description": "Computer equipment and supplies",
                "selected": True
            },
            "30100000": {
                "description": "Office machinery, equipment and supplies except computers, printers and furniture",
                "selected": True
            }
        }
    },
    # Radio, television, communication equipment
    "32000000": {
        "description": "Radio, television, communication, telecommunication and related equipment",
        "selected": False
    },
    # Security and defence equipment
    "35000000": {
        "description": "Security, fire-fighting, police and defence equipment",
        "selected": False
    },
    # Software packages
    "48000000": {
        "description": "Software package and information systems",
        "selected": True
    },
    # IT Services
    "72000000": {
        "description": "IT services: consulting, software development, Internet and support",
        "selected": True
    }
}

# Get list of selected CPV codes (flattened)
def get_selected_cpv_codes():
    """Extract all selected CPV codes including subcodes."""
    selected = []
    for code, data in CPV_CODES.items():
        if data.get("selected", False):
            selected.append(code)
        if "subcodes" in data:
            for subcode, subdata in data["subcodes"].items():
                if subdata.get("selected", False):
                    selected.append(subcode)
    return list(set(selected))  # Remove duplicates


# Business sector categories (from the image)
BUSINESS_SECTORS = [
    "agfo",  # Agriculture and Food
    "comp",  # Computer and Related Services
]

# Default pagination settings
DEFAULT_PAGE_SIZE = 50
MAX_RESULTS = 10000  # Maximum results to fetch

# API endpoints (discovered from page analysis)
TED_BASE_URL = "https://ted.europa.eu"
TED_SEARCH_URL = f"{TED_BASE_URL}/en/search/result"
TED_NOTICE_URL = f"{TED_BASE_URL}/en/notice/-/detail"

# Rate limiting settings
REQUEST_DELAY = 1.0  # Seconds between requests
MAX_RETRIES = 3
RETRY_DELAY = 2.0  # Seconds between retries
