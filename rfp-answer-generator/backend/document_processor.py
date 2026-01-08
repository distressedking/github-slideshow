"""
Document Processing Module
Handles extraction of text from various document formats (PDF, DOCX, TXT)
"""

import os
import re
from pathlib import Path
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass


@dataclass
class DocumentChunk:
    """Represents a chunk of document text"""
    content: str
    source_file: str
    chunk_index: int
    metadata: Dict


@dataclass
class ProcessedDocument:
    """Represents a fully processed document"""
    filename: str
    full_text: str
    chunks: List[DocumentChunk]
    metadata: Dict
    document_type: str  # 'rfp' or 'answer'


class DocumentProcessor:
    """Processes various document formats and extracts text"""

    def __init__(self, chunk_size: int = 1000, chunk_overlap: int = 200):
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap

    def extract_text_from_pdf(self, file_path: str) -> str:
        """Extract text from PDF file"""
        try:
            from PyPDF2 import PdfReader

            reader = PdfReader(file_path)
            text_parts = []

            for page_num, page in enumerate(reader.pages):
                page_text = page.extract_text()
                if page_text:
                    text_parts.append(f"[Page {page_num + 1}]\n{page_text}")

            return "\n\n".join(text_parts)
        except ImportError:
            raise ImportError("PyPDF2 is required for PDF processing. Install with: pip install PyPDF2")
        except Exception as e:
            raise Exception(f"Error extracting text from PDF: {str(e)}")

    def extract_text_from_docx(self, file_path: str) -> str:
        """Extract text from DOCX file"""
        try:
            from docx import Document

            doc = Document(file_path)
            text_parts = []

            for para in doc.paragraphs:
                if para.text.strip():
                    text_parts.append(para.text)

            # Also extract text from tables
            for table in doc.tables:
                for row in table.rows:
                    row_text = " | ".join(cell.text.strip() for cell in row.cells if cell.text.strip())
                    if row_text:
                        text_parts.append(row_text)

            return "\n\n".join(text_parts)
        except ImportError:
            raise ImportError("python-docx is required for DOCX processing. Install with: pip install python-docx")
        except Exception as e:
            raise Exception(f"Error extracting text from DOCX: {str(e)}")

    def extract_text_from_txt(self, file_path: str) -> str:
        """Extract text from plain text file"""
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            return f.read()

    def extract_text(self, file_path: str) -> str:
        """Extract text from a document based on its extension"""
        path = Path(file_path)
        extension = path.suffix.lower()

        if extension == '.pdf':
            return self.extract_text_from_pdf(file_path)
        elif extension == '.docx':
            return self.extract_text_from_docx(file_path)
        elif extension in ['.txt', '.md', '.rst']:
            return self.extract_text_from_txt(file_path)
        else:
            # Try reading as text
            try:
                return self.extract_text_from_txt(file_path)
            except Exception:
                raise ValueError(f"Unsupported file format: {extension}")

    def clean_text(self, text: str) -> str:
        """Clean and normalize text"""
        # Remove excessive whitespace
        text = re.sub(r'\s+', ' ', text)
        # Remove special characters that don't add meaning
        text = re.sub(r'[^\w\s.,;:!?\'\"()\-\[\]{}@#$%&*+=/<>]', '', text)
        # Normalize line breaks
        text = re.sub(r'\n{3,}', '\n\n', text)
        return text.strip()

    def chunk_text(self, text: str, source_file: str) -> List[DocumentChunk]:
        """Split text into overlapping chunks"""
        chunks = []
        text = self.clean_text(text)

        if len(text) <= self.chunk_size:
            chunks.append(DocumentChunk(
                content=text,
                source_file=source_file,
                chunk_index=0,
                metadata={"total_chunks": 1}
            ))
            return chunks

        # Split by sentences first for better chunk boundaries
        sentences = re.split(r'(?<=[.!?])\s+', text)

        current_chunk = ""
        chunk_index = 0

        for sentence in sentences:
            if len(current_chunk) + len(sentence) <= self.chunk_size:
                current_chunk += " " + sentence if current_chunk else sentence
            else:
                if current_chunk:
                    chunks.append(DocumentChunk(
                        content=current_chunk.strip(),
                        source_file=source_file,
                        chunk_index=chunk_index,
                        metadata={}
                    ))
                    chunk_index += 1

                    # Create overlap with last portion of previous chunk
                    overlap_text = current_chunk[-self.chunk_overlap:] if len(current_chunk) > self.chunk_overlap else current_chunk
                    current_chunk = overlap_text + " " + sentence
                else:
                    current_chunk = sentence

        # Don't forget the last chunk
        if current_chunk.strip():
            chunks.append(DocumentChunk(
                content=current_chunk.strip(),
                source_file=source_file,
                chunk_index=chunk_index,
                metadata={}
            ))

        # Update metadata with total chunks
        for chunk in chunks:
            chunk.metadata["total_chunks"] = len(chunks)

        return chunks

    def process_document(self, file_path: str, document_type: str = "rfp") -> ProcessedDocument:
        """Process a document and return structured data"""
        path = Path(file_path)

        if not path.exists():
            raise FileNotFoundError(f"Document not found: {file_path}")

        # Extract text
        full_text = self.extract_text(file_path)

        # Create chunks
        chunks = self.chunk_text(full_text, path.name)

        # Build metadata
        metadata = {
            "filename": path.name,
            "extension": path.suffix.lower(),
            "size_bytes": path.stat().st_size,
            "num_chunks": len(chunks),
            "char_count": len(full_text),
            "word_count": len(full_text.split()),
            "document_type": document_type
        }

        return ProcessedDocument(
            filename=path.name,
            full_text=full_text,
            chunks=chunks,
            metadata=metadata,
            document_type=document_type
        )

    def extract_questions_from_rfp(self, text: str) -> List[Dict]:
        """Extract questions or requirements from RFP text"""
        questions = []

        # Common patterns for RFP questions/requirements
        patterns = [
            r'(?:^|\n)\s*(\d+[\.\)]\s*.+?\?)',  # Numbered questions
            r'(?:^|\n)\s*([A-Z][\.\)]\s*.+?\?)',  # Lettered questions
            r'(?:^|\n)\s*((?:Please|Describe|Explain|Provide|List|What|How|Why|When|Where|Who).+?\?)',  # Question starters
            r'(?:^|\n)\s*(?:Requirement|Section)\s*[\d\.]+[:\s]+(.+?)(?=\n|$)',  # Requirement sections
        ]

        for pattern in patterns:
            matches = re.findall(pattern, text, re.IGNORECASE | re.MULTILINE)
            for match in matches:
                if len(match) > 20:  # Filter out very short matches
                    questions.append({
                        "question": match.strip(),
                        "pattern_matched": pattern[:30] + "..."
                    })

        # Deduplicate
        seen = set()
        unique_questions = []
        for q in questions:
            if q["question"] not in seen:
                seen.add(q["question"])
                unique_questions.append(q)

        return unique_questions
