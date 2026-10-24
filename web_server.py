#!/usr/bin/env python3
"""
Launcher for A4KU Discord 7K Badge Farmer.
Redirects to the dedicated web engine located in ./web/server.py.
"""
import sys
from pathlib import Path

WEB_DIR = Path(__file__).resolve().parent / "web"
sys.path.insert(0, str(WEB_DIR))

if __name__ == "__main__":
    from server import run_web
    run_web()
