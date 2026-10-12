#!/usr/bin/env python
"""
Run FastAPI server for IDAMP REST API.

This script starts the FastAPI server on port 8000.
It shares state with the Streamlit UI via APIStateManager.

Usage:
    python app/run_api.py
    
Then access the API at: http://localhost:8000
And interactive docs at: http://localhost:8000/docs
"""

import sys
import os
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# Set up environment
os.environ.setdefault("PYTHONUNBUFFERED", "1")

import uvicorn

if __name__ == "__main__":
    print("\n" + "="*70)
    print("🚀 Starting IDAMP REST API Server")
    print("="*70)
    print("\n📍 API Running at: http://localhost:8000")
    print("📚 Interactive Docs: http://localhost:8000/docs")
    print("📖 ReDoc: http://localhost:8000/redoc")
    print("\n💡 Tip: Open http://localhost:8000/docs to try endpoints interactively")
    print("\n" + "="*70 + "\n")
    
    uvicorn.run(
        "app.api:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info",
    )
