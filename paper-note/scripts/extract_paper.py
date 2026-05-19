#!/usr/bin/env python3
"""
Smart PDF extraction for paper-note skill.
Extracts core content while filtering out references and appendices,
and extracts paper metadata.
"""

from __future__ import annotations

import sys
import re
import logging
import argparse
from pathlib import Path
from dataclasses import dataclass, field
from typing import List, Optional, Tuple, Pattern

# Local imports
from config import (
    __version__,
    load_config,
    setup_logging,
    PaperNoteConfig,
    REFERENCE_HEADERS,
)

# Try to import PyMuPDF
try:
    import fitz  # PyMuPDF
except ImportError:
    print("Error: PyMuPDF not installed. Install with: pip install PyMuPDF")
    sys.exit(1)


# ===========================================
# Data Classes for Extraction Results
# ===========================================

@dataclass
class PaperMetadata:
    """Metadata extracted from a PDF paper."""
    title: Optional[str] = None
    authors: List[str] = field(default_factory=list)
    year: Optional[int] = None
    doi: Optional[str] = None
    arxiv_id: Optional[str] = None
    keywords: List[str] = field(default_factory=list)


@dataclass
class ExtractionResult:
    """Result of PDF extraction."""
    metadata: PaperMetadata
    content: str
    pages_extracted: int
    total_pages: int
    stopped_at_references: bool
    output_path: Optional[Path] = None


# ===========================================
# Citation Patterns
# ===========================================

_CITATION_PATTERNS: List[Pattern] = [
    re.compile(r'^(\[\d+\]|\d+\.)\s+[A-Z]'),  # [1] Author or 1. Author
    re.compile(r'\(\d{4}[a-z]?\)'),  # Year in parentheses like (2020)
    re.compile(r'doi\.org', re.IGNORECASE),  # DOI links
    re.compile(r'arxiv\.org', re.IGNORECASE),  # arXiv links
    re.compile(r'http[s]?://'),  # URLs
]


# ===========================================
# Helper Functions
# ===========================================

def _check_page_position(page_num: int, total_pages: int, threshold: float) -> bool:
    """
    Check if page position meets the threshold.
    
    Args:
        page_num: Current page number (0-based)
        total_pages: Total number of pages in document
        threshold: Position threshold (0.0 to 1.0)
        
    Returns:
        True if page is at or beyond threshold position
    """
    return page_num >= total_pages * threshold


def _count_citation_lines(lines: List[str], max_lines: int) -> Tuple[int, int]:
    """
    Count lines matching any of the citation patterns.
    
    Args:
        lines: List of text lines to check
        max_lines: Maximum number of lines to check
        
    Returns:
        Tuple of (citation_count, lines_checked)
    """
    citation_count = 0
    lines_to_check = min(max_lines, len(lines))

    for line in lines[:lines_to_check]:
        line = line.strip()
        for pattern in _CITATION_PATTERNS:
            if pattern.search(line):
                citation_count += 1
                break  # Count each line only once

    return citation_count, lines_to_check


def _calculate_citation_density(citation_count: int, total_lines: int, threshold: float) -> bool:
    """
    Check if citation density meets the threshold.
    
    Args:
        citation_count: Number of lines with citations
        total_lines: Total lines checked
        threshold: Density threshold (0.0 to 1.0)
        
    Returns:
        True if citation density meets or exceeds threshold
    """
    if total_lines == 0:
        return False
    return citation_count >= total_lines * threshold


# ===========================================
# Reference Detection Functions
# ===========================================

def is_references_section(text: str, page_num: int, total_pages: int, config: PaperNoteConfig) -> bool:
    """
    Detect if we've reached the references section.
    
    Args:
        text: Text content of the page
        page_num: Current page number (0-based)
        total_pages: Total number of pages in document
        config: Configuration object
        
    Returns:
        True if references section detected
    """
    lines = text.strip().split('\n')
    if len(lines) == 0:
        return False

    # Check ALL lines for explicit "REFERENCES" header
    # This handles cases where page markers or blank lines precede the header
    # Also handles cases where ACKNOWLEDGEMENTS, ETHICS STATEMENT come first
    for line in lines[:config.extraction.max_lines_to_check]:
        line_clean = line.strip().upper()
        if line_clean in REFERENCE_HEADERS:
            return True
        if re.match(r'^REFERENCES\s*\d+$', line_clean):
            return True

    # Only check for reference page pattern if we're past threshold of the paper
    if not _check_page_position(page_num, total_pages, config.extraction.page_position_threshold):
        return False

    # Check if page starts with numbered references pattern
    first_non_empty = None
    for line in lines:
        stripped = line.strip()
        if stripped and not stripped.startswith('--- Page'):
            first_non_empty = stripped
            break

    if first_non_empty and re.match(r'^(\[\d+\]|\d+\.)\s+[A-Z]', first_non_empty):
        # Additional check: look for strong citation pattern
        citation_count, total_checked = _count_citation_lines(lines, config.extraction.citation_check_lines)
        if _calculate_citation_density(citation_count, total_checked, config.extraction.citation_density_threshold):
            return True

    return False


def is_likely_reference_page(text: str, page_num: int, total_pages: int, config: PaperNoteConfig) -> bool:
    """
    Heuristic to detect if a page is mostly references.
    
    Args:
        text: Text content of the page
        page_num: Current page number (0-based)
        total_pages: Total number of pages in document
        config: Configuration object
        
    Returns:
        True if page is likely mostly references
    """
    # Only apply this check in the last section of the paper
    if not _check_page_position(page_num, total_pages, config.extraction.last_section_threshold):
        return False

    lines = text.strip().split('\n')
    if len(lines) < 5:
        return False

    # Count lines that look like citations
    citation_count, lines_to_check = _count_citation_lines(lines, config.extraction.reference_page_check_lines)
    return _calculate_citation_density(citation_count, lines_to_check, config.extraction.reference_page_threshold)


# ===========================================
# Metadata Extraction Functions
# ===========================================

def extract_metadata(doc: fitz.Document, first_page_text: str, config: PaperNoteConfig) -> PaperMetadata:
    """
    Extract metadata from PDF document.

    Args:
        doc: PyMuPDF document object
        first_page_text: Text from first page for additional parsing
        config: Configuration object

    Returns:
        PaperMetadata object with extracted metadata
    """
    metadata = PaperMetadata()

    # Extract from PDF document info
    doc_info = doc.metadata

    if doc_info.get('title'):
        metadata.title = doc_info['title'].strip()

    if doc_info.get('author'):
        authors_str = doc_info['author']
        # Split on common separators
        for sep in [' and ', ', ', '; ']:
            if sep in authors_str:
                metadata.authors = [a.strip() for a in authors_str.split(sep) if a.strip()]
                break
        else:
            metadata.authors = [authors_str.strip()] if authors_str.strip() else []

    # Try to extract year from various sources
    if doc_info.get('creationDate'):
        # Creation date format: D:20240101000000
        year_match = re.search(r'D:(\d{4})', doc_info['creationDate'])
        if year_match:
            year = int(year_match.group(1))
            if config.extraction.min_year <= year <= config.extraction.max_year:
                metadata.year = year

    # Parse additional metadata from first page text
    _parse_metadata_from_text(first_page_text, metadata, config)

    return metadata


def _parse_metadata_from_text(text: str, metadata: PaperMetadata, config: PaperNoteConfig) -> None:
    """
    Parse additional metadata from first page text.

    Args:
        text: Text to parse
        metadata: PaperMetadata object to update
        config: Configuration object containing year range settings
    """
    lines = [line.strip() for line in text.split('\n') if line.strip()]

    # Extract title if not already found (take first non-empty line as heuristic)
    if not metadata.title and lines:
        # Look for a line that looks like a title (not too short, not too long)
        for line in lines[:10]:
            if 10 < len(line) < 200 and not line.startswith('http'):
                metadata.title = line
                break

    # Extract DOI
    doi_match = re.search(r'(?:doi:|https?://doi\.org/)([^\s]+)', text, re.IGNORECASE)
    if doi_match:
        metadata.doi = doi_match.group(1).strip()

    # Extract arXiv ID
    arxiv_match = re.search(r'arXiv:(\d+\.\d+)(v\d+)?', text, re.IGNORECASE)
    if arxiv_match:
        metadata.arxiv_id = arxiv_match.group(1)

    # Extract year if not found from metadata
    if not metadata.year:
        # Look for 4-digit year in reasonable range
        year_match = re.search(r'\b(19|20)\d{2}\b', text)
        if year_match:
            year = int(year_match.group(0))
            if config.extraction.min_year <= year <= config.extraction.max_year:
                metadata.year = year


# ===========================================
# Main Extraction Function
# ===========================================

def generate_unique_output_path(pdf_path: Path, base_dir: Optional[Path] = None) -> Path:
    """
    Generate a unique output path based on PDF file path.
    
    Uses a hash of the absolute PDF path to ensure unique temp files
    for concurrent processing.
    
    Args:
        pdf_path: Path to the PDF file
        base_dir: Optional base directory for output (defaults to current directory)
        
    Returns:
        Unique Path object for the temp output file
    """
    import hashlib
    
    if base_dir is None:
        base_dir = Path(".")
    
    pdf_name = pdf_path.stem
    pdf_abs_path = str(pdf_path.resolve())
    path_hash = hashlib.md5(pdf_abs_path.encode()).hexdigest()[:8]
    
    safe_name = re.sub(r'[^\w\-_.]', '_', pdf_name)
    
    unique_name = f"paper_note_{safe_name}_{path_hash}.txt"
    
    return base_dir / unique_name


def extract_paper_content(
    pdf_path: Path,
    output_path: Optional[Path] = None,
    max_pages: Optional[int] = None,
    config: Optional[PaperNoteConfig] = None,
    logger: Optional[logging.Logger] = None,
) -> ExtractionResult:
    """
    Extract core paper content, stopping at references.
    
    Args:
        pdf_path: Path to PDF file
        output_path: Path to save extracted text (optional)
        max_pages: Maximum pages to extract (optional, for very long papers)
        config: Configuration object (optional, uses defaults if not provided)
        logger: Logger instance (optional, creates new if not provided)
        
    Returns:
        ExtractionResult with extracted content and metadata
        
    Raises:
        FileNotFoundError: If PDF file does not exist
        ValueError: If PDF is invalid
        Exception: For other extraction errors
    """
    if config is None:
        config = load_config()
    
    if logger is None:
        logger = setup_logging(config.logging)
    
    pdf_path = Path(pdf_path)
    
    if not pdf_path.exists():
        logger.error(f"PDF file not found: {pdf_path}")
        raise FileNotFoundError(f"PDF file not found: {pdf_path}")
    
    logger.info(f"Processing PDF: {pdf_path.name}")
    
    # Open PDF
    try:
        with fitz.open(str(pdf_path)) as doc:
            total_pages = len(doc)
            logger.info(f"Total pages: {total_pages}")
            
            if total_pages == 0:
                logger.error("PDF has no pages")
                raise ValueError("PDF has no pages")
            
            # Extract metadata
            first_page_text = doc[0].get_text()
            metadata = extract_metadata(doc, first_page_text, config)
            
            if metadata.title:
                logger.info(f"Title: {metadata.title}")
            if metadata.authors:
                logger.info(f"Authors: {', '.join(metadata.authors)}")
            if metadata.year:
                logger.info(f"Year: {metadata.year}")
            
            extracted_text = []
            stop_page = None
            
            # Determine how many pages to process
            pages_to_process = min(total_pages, max_pages) if max_pages else total_pages
            
            for page_num in range(pages_to_process):
                page = doc[page_num]
                text = page.get_text()
                
                # Check if we've hit references section
                if config.extraction.stop_at_references:
                    if (is_references_section(text, page_num, total_pages, config) or 
                        is_likely_reference_page(text, page_num, total_pages, config)):
                        stop_page = page_num + 1
                        logger.info(f"Stopping at page {stop_page} (references section detected)")
                        break
                
                # Add page marker for readability
                if config.extraction.include_page_markers:
                    extracted_text.append(f"\n--- Page {page_num + 1} ---\n")
                extracted_text.append(text)
            
            # Process results inside with block
            if stop_page is None:
                stop_page = pages_to_process
            
            final_text = '\n'.join(extracted_text)
            
            # Clean up excessive whitespace
            final_text = re.sub(r'\n{3,}', '\n\n', final_text)
            
            logger.info(f"Extracted {stop_page} pages (skipped {total_pages - stop_page} pages)")
            
            result = ExtractionResult(
                metadata=metadata,
                content=final_text,
                pages_extracted=stop_page,
                total_pages=total_pages,
                stopped_at_references=stop_page < total_pages,
            )
            
            # Save to file if output path provided
            if output_path:
                output_path = Path(output_path)
                try:
                    output_path.write_text(final_text, encoding=config.output.encoding)
                    result.output_path = output_path
                    logger.info(f"Saved to: {output_path}")
                except Exception as e:
                    logger.error(f"Failed to save output: {e}")
                    raise
            
            return result
    except Exception as e:
        logger.error(f"Failed to process PDF: {e}")
        raise

def main() -> int:
    """
    Main entry point for CLI.
    
    Returns:
        Exit code (0 for success, non-zero for failure)
    """
    parser = argparse.ArgumentParser(
        description="Smart PDF extraction for paper-note skill"
    )
    
    parser.add_argument(
        "--version",
        action="version",
        version=f"paper-note extract_paper v{__version__}"
    )
    
    parser.add_argument(
        "pdf_path",
        type=Path,
        help="Path to PDF file"
    )
    
    parser.add_argument(
        "output_path",
        type=Path,
        nargs="?",
        default=None,
        help="Path to save extracted text (default: unique temp file based on PDF path)"
    )
    
    parser.add_argument(
        "--max-pages",
        type=int,
        default=None,
        help="Maximum pages to extract (for very long papers)"
    )
    
    parser.add_argument(
        "--config",
        type=Path,
        default=None,
        help="Path to JSON configuration file"
    )
    
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Enable verbose logging"
    )
    
    parser.add_argument(
        "-q",
        "--quiet",
        action="store_true",
        help="Suppress non-error output"
    )
    
    args = parser.parse_args()
    
    # Load configuration
    try:
        config = load_config(args.config)
    except Exception as e:
        print(f"Error loading configuration: {e}", file=sys.stderr)
        return 1
    
    # Adjust logging level based on flags
    if args.verbose:
        config.logging.level = logging.DEBUG
    elif args.quiet:
        config.logging.level = logging.ERROR
    
    logger = setup_logging(config.logging)
    
    # Validate inputs
    if not args.pdf_path.exists():
        logger.error(f"PDF file not found: {args.pdf_path}")
        return 1
    
    if args.pdf_path.suffix.lower() != ".pdf":
        logger.warning(f"Input file does not have .pdf extension: {args.pdf_path}")
    
    # Generate unique output path if not provided
    output_path = args.output_path
    if output_path is None:
        output_path = generate_unique_output_path(args.pdf_path)
        logger.info(f"Using unique output path: {output_path}")
    
    # Run extraction
    try:
        extract_paper_content(
            pdf_path=args.pdf_path,
            output_path=output_path,
            max_pages=args.max_pages,
            config=config,
            logger=logger,
        )
        return 0
    except Exception as e:
        logger.error(f"Extraction failed: {e}", exc_info=args.verbose)
        return 1


if __name__ == '__main__':
    sys.exit(main())
