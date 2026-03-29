#!/usr/bin/env python3
import os
from pathlib import Path
import psycopg

BASE = Path(__file__).resolve().parents[1]
SQL = (BASE / 'scripts' / 'aggregate_tree_stats.sql').read_text()

url = os.getenv('DATABASE_URL', 'postgresql://app:app@localhost:5432/chess_teacher_ai')
url = url.replace('postgresql+psycopg', 'postgresql')

with psycopg.connect(url) as conn, conn.cursor() as cur:
    cur.execute(SQL)
    conn.commit()

print('ok: aggregated position_move_stats')
