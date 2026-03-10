"""CLI entry point for analyzing experiment results."""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from analysis.report import generate_report

if __name__ == "__main__":
    generate_report()
