#!/usr/bin/env python3
"""
RFP Answer Generator - Startup Script
"""

import os
import sys
from pathlib import Path

# Ensure we're in the right directory
os.chdir(Path(__file__).parent)

# Check Python version
if sys.version_info < (3, 9):
    print("Error: Python 3.9 or higher is required")
    sys.exit(1)

def check_dependencies():
    """Check if required packages are installed"""
    required = ['fastapi', 'uvicorn', 'sentence_transformers', 'chromadb']
    missing = []

    for package in required:
        try:
            __import__(package.replace('-', '_'))
        except ImportError:
            missing.append(package)

    if missing:
        print("Missing dependencies detected!")
        print("Please install with: pip install -r requirements.txt")
        print(f"Missing: {', '.join(missing)}")
        return False

    return True


def main():
    """Start the RFP Answer Generator"""
    print("=" * 50)
    print("  RFP Answer Generator")
    print("=" * 50)

    # Check dependencies
    if not check_dependencies():
        sys.exit(1)

    print("\nStarting server...")
    print("Open http://localhost:8000 in your browser\n")

    import uvicorn
    uvicorn.run(
        "backend.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )


if __name__ == "__main__":
    main()
