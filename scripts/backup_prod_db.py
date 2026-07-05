#!/usr/bin/env python
"""Backup production database before deployment."""
import os, sys, shutil, datetime

BACKUP_DIR = os.path.join(os.path.dirname(__file__), '..', 'backups')
os.makedirs(BACKUP_DIR, exist_ok=True)

DB_PATH = os.environ.get('ETF_DB_PATH') or os.path.join(os.path.dirname(__file__), '..', 'data', 'etf.duckdb')
TS = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
BACKUP_FILE = os.path.join(BACKUP_DIR, f'etf_backup_{TS}.duckdb')

if os.path.exists(DB_PATH):
    shutil.copy2(DB_PATH, BACKUP_FILE)
    size_mb = os.path.getsize(BACKUP_FILE) / 1024 / 1024
    print(f'Backup created: {BACKUP_FILE} ({size_mb:.1f} MB)')
else:
    print(f'ERROR: DB not found at {DB_PATH}')
    sys.exit(1)