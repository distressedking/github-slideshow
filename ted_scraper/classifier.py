"""
Tender Classification Module.

This module provides various methods for classifying and categorizing
tender notices scraped from TED Europa.

Classification approaches:
1. Rule-based: Using keywords and CPV codes
2. ML-based: Using text classification models (optional)
3. LLM-based: Using language models for complex categorization (optional)
"""

import re
from typing import List, Dict, Any, Optional, Callable
from dataclasses import dataclass, field
from collections import defaultdict

from models.tender import Tender, TenderCollection


@dataclass
class ClassificationRule:
    """A rule for classifying tenders."""
    name: str
    category: str
    keywords: List[str] = field(default_factory=list)
    cpv_prefixes: List[str] = field(default_factory=list)
    negative_keywords: List[str] = field(default_factory=list)
    priority: int = 1  # Higher priority rules are checked first
    min_keyword_matches: int = 1


# Predefined classification rules for airport-related tenders
AIRPORT_CLASSIFICATION_RULES = [
    ClassificationRule(
        name="IT Infrastructure",
        category="IT_INFRASTRUCTURE",
        keywords=["server", "network", "infrastructure", "data center", "cloud", "hosting", "storage"],
        cpv_prefixes=["302", "482", "720"],
        priority=2
    ),
    ClassificationRule(
        name="Security Systems",
        category="SECURITY_SYSTEMS",
        keywords=["security", "surveillance", "cctv", "access control", "screening", "scanner", "x-ray"],
        cpv_prefixes=["350", "351", "352"],
        priority=2
    ),
    ClassificationRule(
        name="Software Development",
        category="SOFTWARE_DEVELOPMENT",
        keywords=["software", "application", "development", "system", "platform", "portal", "app"],
        cpv_prefixes=["480", "722"],
        priority=2
    ),
    ClassificationRule(
        name="Hardware & Equipment",
        category="HARDWARE_EQUIPMENT",
        keywords=["computer", "hardware", "equipment", "device", "terminal", "workstation", "printer"],
        cpv_prefixes=["301", "302", "321"],
        priority=2
    ),
    ClassificationRule(
        name="Consulting & Services",
        category="CONSULTING_SERVICES",
        keywords=["consulting", "advisory", "support", "maintenance", "service", "professional"],
        cpv_prefixes=["721", "723", "724"],
        priority=1
    ),
    ClassificationRule(
        name="Communication Systems",
        category="COMMUNICATION_SYSTEMS",
        keywords=["communication", "radio", "telecommunication", "telephone", "voip", "network"],
        cpv_prefixes=["320", "322", "323"],
        priority=2
    ),
    ClassificationRule(
        name="Baggage Handling",
        category="BAGGAGE_HANDLING",
        keywords=["baggage", "luggage", "handling", "conveyor", "sorting", "belt"],
        cpv_prefixes=["341", "425"],
        priority=3
    ),
    ClassificationRule(
        name="Passenger Systems",
        category="PASSENGER_SYSTEMS",
        keywords=["passenger", "check-in", "boarding", "gate", "kiosk", "self-service", "biometric"],
        cpv_prefixes=["302", "480"],
        priority=3
    ),
    ClassificationRule(
        name="Flight Information",
        category="FLIGHT_INFORMATION",
        keywords=["flight", "display", "fids", "information", "schedule", "departure", "arrival"],
        cpv_prefixes=["302", "323"],
        priority=3
    ),
    ClassificationRule(
        name="Ground Support",
        category="GROUND_SUPPORT",
        keywords=["ground", "support", "vehicle", "handling", "ramp", "apron"],
        cpv_prefixes=["341", "342"],
        priority=2
    ),
]


class TenderClassifier:
    """
    Classifier for categorizing tender notices.

    Supports rule-based classification with customizable rules,
    and optional ML/LLM-based classification.
    """

    def __init__(
        self,
        rules: Optional[List[ClassificationRule]] = None,
        default_category: str = "UNCATEGORIZED"
    ):
        """
        Initialize the classifier.

        Args:
            rules: List of classification rules (uses defaults if None)
            default_category: Category for tenders that don't match any rule
        """
        self.rules = rules or AIRPORT_CLASSIFICATION_RULES
        self.default_category = default_category
        # Sort rules by priority (highest first)
        self.rules.sort(key=lambda r: r.priority, reverse=True)

    def _text_matches_keywords(
        self,
        text: str,
        keywords: List[str],
        min_matches: int = 1
    ) -> tuple[bool, int]:
        """Check if text contains enough keyword matches."""
        text_lower = text.lower()
        matches = sum(1 for kw in keywords if kw.lower() in text_lower)
        return matches >= min_matches, matches

    def _cpv_matches(self, cpv_codes: List[str], cpv_prefixes: List[str]) -> bool:
        """Check if any CPV code matches the prefixes."""
        for code in cpv_codes:
            for prefix in cpv_prefixes:
                if code.startswith(prefix):
                    return True
        return False

    def _has_negative_keywords(self, text: str, negative_keywords: List[str]) -> bool:
        """Check if text contains any negative keywords."""
        if not negative_keywords:
            return False
        text_lower = text.lower()
        return any(kw.lower() in text_lower for kw in negative_keywords)

    def classify_tender(self, tender: Tender) -> tuple[str, float, List[str]]:
        """
        Classify a single tender.

        Args:
            tender: Tender object to classify

        Returns:
            Tuple of (category, confidence_score, matched_tags)
        """
        # Combine searchable text
        searchable_text = f"{tender.title} {tender.description}"

        best_category = self.default_category
        best_score = 0.0
        matched_tags = []

        for rule in self.rules:
            # Check for negative keywords first
            if self._has_negative_keywords(searchable_text, rule.negative_keywords):
                continue

            # Calculate score based on keyword and CPV matches
            keyword_match, keyword_count = self._text_matches_keywords(
                searchable_text,
                rule.keywords,
                rule.min_keyword_matches
            )

            cpv_match = self._cpv_matches(tender.cpv_codes, rule.cpv_prefixes)

            # Calculate confidence score
            if keyword_match or cpv_match:
                score = 0.0

                if keyword_match:
                    # More keyword matches = higher score
                    score += 0.3 + (0.1 * min(keyword_count, 5))
                    matched_tags.extend([kw for kw in rule.keywords
                                        if kw.lower() in searchable_text.lower()])

                if cpv_match:
                    score += 0.4

                # Adjust by priority
                score *= (1 + rule.priority * 0.1)

                if score > best_score:
                    best_score = min(score, 1.0)
                    best_category = rule.category
                    matched_tags = list(set(matched_tags))  # Remove duplicates

        return best_category, best_score, matched_tags

    def classify_collection(self, collection: TenderCollection) -> TenderCollection:
        """
        Classify all tenders in a collection.

        Args:
            collection: TenderCollection to classify

        Returns:
            Updated TenderCollection with classification data
        """
        for tender in collection.tenders:
            category, score, tags = self.classify_tender(tender)
            tender.classification_category = category
            tender.classification_score = score
            tender.classification_tags = tags

        return collection

    def get_category_distribution(self, collection: TenderCollection) -> Dict[str, int]:
        """Get distribution of tenders across categories."""
        distribution = defaultdict(int)
        for tender in collection.tenders:
            distribution[tender.classification_category] += 1
        return dict(distribution)


class KeywordExtractor:
    """Extract and analyze keywords from tender collections."""

    def __init__(self, min_frequency: int = 2, max_keywords: int = 100):
        """
        Initialize keyword extractor.

        Args:
            min_frequency: Minimum times a keyword must appear
            max_keywords: Maximum keywords to return
        """
        self.min_frequency = min_frequency
        self.max_keywords = max_keywords

        # Common stop words to filter out
        self.stop_words = {
            'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for',
            'of', 'with', 'by', 'from', 'as', 'is', 'was', 'are', 'were', 'been',
            'be', 'have', 'has', 'had', 'do', 'does', 'did', 'will', 'would',
            'could', 'should', 'may', 'might', 'must', 'shall', 'can', 'this',
            'that', 'these', 'those', 'it', 'its', 'they', 'them', 'their',
            'we', 'us', 'our', 'you', 'your', 'he', 'she', 'him', 'her', 'his',
            'who', 'which', 'what', 'when', 'where', 'why', 'how', 'all', 'each',
            'every', 'both', 'few', 'more', 'most', 'other', 'some', 'such', 'no',
            'not', 'only', 'same', 'so', 'than', 'too', 'very', 'just', 'also',
            'now', 'here', 'there', 'then', 'once', 'if', 'else', 'when', 'up',
            'down', 'out', 'into', 'over', 'under', 'again', 'further', 'then',
            'contract', 'notice', 'tender', 'procurement', 'services', 'works',
            'supplies', 'provision', 'supply', 'delivery', 'framework', 'agreement'
        }

    def extract_keywords(self, collection: TenderCollection) -> List[tuple[str, int]]:
        """
        Extract top keywords from tender collection.

        Args:
            collection: TenderCollection to analyze

        Returns:
            List of (keyword, frequency) tuples sorted by frequency
        """
        word_freq = defaultdict(int)

        for tender in collection.tenders:
            text = f"{tender.title} {tender.description}".lower()
            # Extract words (alphanumeric, 3+ chars)
            words = re.findall(r'\b[a-z]{3,}\b', text)

            for word in words:
                if word not in self.stop_words:
                    word_freq[word] += 1

        # Filter and sort
        filtered = [(word, freq) for word, freq in word_freq.items()
                   if freq >= self.min_frequency]
        sorted_keywords = sorted(filtered, key=lambda x: x[1], reverse=True)

        return sorted_keywords[:self.max_keywords]

    def extract_bigrams(self, collection: TenderCollection) -> List[tuple[str, int]]:
        """
        Extract top bigrams (2-word phrases) from tender collection.

        Args:
            collection: TenderCollection to analyze

        Returns:
            List of (bigram, frequency) tuples sorted by frequency
        """
        bigram_freq = defaultdict(int)

        for tender in collection.tenders:
            text = f"{tender.title} {tender.description}".lower()
            words = re.findall(r'\b[a-z]{3,}\b', text)
            words = [w for w in words if w not in self.stop_words]

            # Create bigrams
            for i in range(len(words) - 1):
                bigram = f"{words[i]} {words[i+1]}"
                bigram_freq[bigram] += 1

        # Filter and sort
        filtered = [(bg, freq) for bg, freq in bigram_freq.items()
                   if freq >= self.min_frequency]
        sorted_bigrams = sorted(filtered, key=lambda x: x[1], reverse=True)

        return sorted_bigrams[:self.max_keywords]


class CPVAnalyzer:
    """Analyze CPV code distribution in tender collections."""

    # CPV code divisions (first 2 digits)
    CPV_DIVISIONS = {
        '03': 'Agricultural products',
        '09': 'Petroleum products, fuel, electricity',
        '14': 'Mining, basic metals',
        '15': 'Food, beverages, tobacco',
        '18': 'Clothing, footwear, luggage',
        '19': 'Leather and textile fabrics',
        '22': 'Printed matter and related',
        '24': 'Chemical products',
        '30': 'Office and computing machinery',
        '31': 'Electrical machinery',
        '32': 'Radio, television, communication',
        '33': 'Medical equipment',
        '34': 'Transport equipment',
        '35': 'Security, defence equipment',
        '37': 'Musical instruments, sport goods',
        '38': 'Laboratory, optical equipment',
        '39': 'Furniture, furnishings',
        '41': 'Collected and purified water',
        '42': 'Industrial machinery',
        '43': 'Machinery for mining',
        '44': 'Construction structures',
        '45': 'Construction work',
        '48': 'Software packages',
        '50': 'Repair and maintenance',
        '51': 'Installation services',
        '55': 'Hotel and restaurant',
        '60': 'Transport services',
        '63': 'Supporting transport services',
        '64': 'Postal and telecommunications',
        '65': 'Public utilities',
        '66': 'Financial and insurance',
        '70': 'Real estate services',
        '71': 'Architectural, engineering',
        '72': 'IT services',
        '73': 'Research and development',
        '75': 'Administration, defence, social',
        '76': 'Services related to oil and gas',
        '77': 'Agricultural, forestry services',
        '79': 'Business services',
        '80': 'Education and training',
        '85': 'Health and social work',
        '90': 'Sewage, refuse, cleaning',
        '92': 'Recreational, cultural, sporting',
        '98': 'Other community, social services',
    }

    def analyze(self, collection: TenderCollection) -> Dict[str, Any]:
        """
        Analyze CPV code distribution in collection.

        Args:
            collection: TenderCollection to analyze

        Returns:
            Dictionary with CPV analysis results
        """
        division_counts = defaultdict(int)
        full_code_counts = defaultdict(int)
        tenders_by_division = defaultdict(list)

        for tender in collection.tenders:
            for cpv_code in tender.cpv_codes:
                if len(cpv_code) >= 2:
                    division = cpv_code[:2]
                    division_counts[division] += 1
                    tenders_by_division[division].append(tender.notice_id)

                full_code_counts[cpv_code] += 1

        # Convert to labeled results
        labeled_divisions = {}
        for div, count in division_counts.items():
            label = self.CPV_DIVISIONS.get(div, f'Unknown ({div})')
            labeled_divisions[f"{div} - {label}"] = count

        # Sort by count
        labeled_divisions = dict(sorted(
            labeled_divisions.items(),
            key=lambda x: x[1],
            reverse=True
        ))

        top_codes = dict(sorted(
            full_code_counts.items(),
            key=lambda x: x[1],
            reverse=True
        )[:20])

        return {
            'division_distribution': labeled_divisions,
            'top_cpv_codes': top_codes,
            'total_unique_divisions': len(division_counts),
            'total_unique_codes': len(full_code_counts)
        }
