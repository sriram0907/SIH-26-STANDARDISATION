#!/bin/bash
# Launch script for Material Code Harmonization Platform
# Deletes old DB to force fresh pipeline run with new procurement data
cd "$(dirname "$0")"
source .venv/bin/activate

# Delete old DB to force pipeline re-run (keeps regenerated CSV data)
rm -f db/harmonize.db

python run.py
