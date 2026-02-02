"""
Data models for TED Europa tender notices.
"""

from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import Optional, List, Dict, Any
import json


@dataclass
class Tender:
    """Represents a single tender notice from TED Europa."""

    # Core identifiers
    notice_id: str
    publication_number: str = ""

    # Basic information
    title: str = ""
    description: str = ""

    # Dates
    publication_date: Optional[datetime] = None
    submission_deadline: Optional[datetime] = None

    # Classification
    cpv_codes: List[str] = field(default_factory=list)
    cpv_descriptions: List[str] = field(default_factory=list)
    notice_type: str = ""  # e.g., "Contract notice", "Contract award"
    procedure_type: str = ""  # e.g., "Open procedure", "Restricted procedure"

    # Buyer information
    buyer_name: str = ""
    buyer_country: str = ""
    buyer_city: str = ""

    # Contract details
    estimated_value: Optional[float] = None
    currency: str = "EUR"
    contract_location: str = ""

    # URLs
    notice_url: str = ""
    document_url: str = ""

    # Raw data for reference
    raw_data: Dict[str, Any] = field(default_factory=dict)

    # Classification fields (to be filled during analysis)
    classification_category: str = ""
    classification_score: float = 0.0
    classification_tags: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """Convert tender to dictionary for JSON serialization."""
        data = asdict(self)
        # Convert datetime objects to ISO format strings
        if self.publication_date:
            data['publication_date'] = self.publication_date.isoformat()
        if self.submission_deadline:
            data['submission_deadline'] = self.submission_deadline.isoformat()
        return data

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Tender':
        """Create Tender from dictionary."""
        # Parse datetime strings back to datetime objects
        if data.get('publication_date') and isinstance(data['publication_date'], str):
            data['publication_date'] = datetime.fromisoformat(data['publication_date'])
        if data.get('submission_deadline') and isinstance(data['submission_deadline'], str):
            data['submission_deadline'] = datetime.fromisoformat(data['submission_deadline'])
        return cls(**data)

    def matches_keywords(self, keywords: List[str]) -> bool:
        """Check if tender matches any of the given keywords."""
        text = f"{self.title} {self.description}".lower()
        return any(kw.lower() in text for kw in keywords)

    def has_cpv_code(self, cpv_code: str) -> bool:
        """Check if tender has a specific CPV code (including partial matches)."""
        return any(code.startswith(cpv_code) for code in self.cpv_codes)


@dataclass
class TenderCollection:
    """Collection of tenders with utility methods."""

    tenders: List[Tender] = field(default_factory=list)
    search_query: str = ""
    search_date: Optional[datetime] = None
    total_results: int = 0

    def add(self, tender: Tender) -> None:
        """Add a tender to the collection."""
        self.tenders.append(tender)

    def filter_by_cpv(self, cpv_code: str) -> 'TenderCollection':
        """Filter tenders by CPV code prefix."""
        filtered = [t for t in self.tenders if t.has_cpv_code(cpv_code)]
        return TenderCollection(
            tenders=filtered,
            search_query=f"{self.search_query} (CPV: {cpv_code})",
            search_date=self.search_date,
            total_results=len(filtered)
        )

    def filter_by_country(self, country: str) -> 'TenderCollection':
        """Filter tenders by buyer country."""
        filtered = [t for t in self.tenders if t.buyer_country.lower() == country.lower()]
        return TenderCollection(
            tenders=filtered,
            search_query=f"{self.search_query} (Country: {country})",
            search_date=self.search_date,
            total_results=len(filtered)
        )

    def filter_by_keywords(self, keywords: List[str]) -> 'TenderCollection':
        """Filter tenders containing any of the keywords."""
        filtered = [t for t in self.tenders if t.matches_keywords(keywords)]
        return TenderCollection(
            tenders=filtered,
            search_query=f"{self.search_query} (Keywords: {keywords})",
            search_date=self.search_date,
            total_results=len(filtered)
        )

    def to_json(self, filepath: str) -> None:
        """Export collection to JSON file."""
        data = {
            'search_query': self.search_query,
            'search_date': self.search_date.isoformat() if self.search_date else None,
            'total_results': self.total_results,
            'tenders': [t.to_dict() for t in self.tenders]
        }
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

    @classmethod
    def from_json(cls, filepath: str) -> 'TenderCollection':
        """Load collection from JSON file."""
        with open(filepath, 'r', encoding='utf-8') as f:
            data = json.load(f)

        tenders = [Tender.from_dict(t) for t in data.get('tenders', [])]
        return cls(
            tenders=tenders,
            search_query=data.get('search_query', ''),
            search_date=datetime.fromisoformat(data['search_date']) if data.get('search_date') else None,
            total_results=data.get('total_results', len(tenders))
        )

    def to_csv(self, filepath: str) -> None:
        """Export collection to CSV file."""
        import csv

        if not self.tenders:
            return

        fieldnames = [
            'notice_id', 'publication_number', 'title', 'notice_type',
            'buyer_name', 'buyer_country', 'publication_date',
            'submission_deadline', 'estimated_value', 'currency',
            'cpv_codes', 'procedure_type', 'notice_url',
            'classification_category', 'classification_tags'
        ]

        with open(filepath, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction='ignore')
            writer.writeheader()
            for tender in self.tenders:
                row = tender.to_dict()
                row['cpv_codes'] = '; '.join(row.get('cpv_codes', []))
                row['classification_tags'] = '; '.join(row.get('classification_tags', []))
                writer.writerow(row)

    def summary(self) -> Dict[str, Any]:
        """Generate summary statistics for the collection."""
        countries = {}
        cpv_counts = {}
        notice_types = {}

        for tender in self.tenders:
            # Count by country
            country = tender.buyer_country or 'Unknown'
            countries[country] = countries.get(country, 0) + 1

            # Count by CPV
            for cpv in tender.cpv_codes:
                cpv_prefix = cpv[:2] if cpv else 'Unknown'
                cpv_counts[cpv_prefix] = cpv_counts.get(cpv_prefix, 0) + 1

            # Count by notice type
            notice_type = tender.notice_type or 'Unknown'
            notice_types[notice_type] = notice_types.get(notice_type, 0) + 1

        return {
            'total_tenders': len(self.tenders),
            'countries': countries,
            'cpv_distribution': cpv_counts,
            'notice_types': notice_types
        }

    def __len__(self) -> int:
        return len(self.tenders)

    def __iter__(self):
        return iter(self.tenders)
