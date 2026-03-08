"""
Entry Point — EconoGrid Planner.

Start the Flask dashboard server.

Usage:
    python run.py

Then open http://localhost:5000 in your browser.
"""

import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(__file__))

from dashboard.app import create_app
from config import FLASK_HOST, FLASK_PORT, FLASK_DEBUG


def main():
    """Start the EconoGrid Planner dashboard server."""
    print("=" * 60)
    print("  ⚡  EconoGrid Planner")
    print("=" * 60)
    print(f"  Server:  http://{FLASK_HOST}:{FLASK_PORT}")
    print(f"  Debug:   {FLASK_DEBUG}")
    print("  Modules: EViews | LEAP | RETScreen")
    print("=" * 60)
    print()

    app = create_app()
    app.run(host=FLASK_HOST, port=FLASK_PORT, debug=FLASK_DEBUG)


if __name__ == "__main__":
    main()
