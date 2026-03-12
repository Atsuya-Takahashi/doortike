import os
import sys
from sqlalchemy import create_engine, text

# Load from backend/.env
with open('backend/.env') as f:
    for line in f:
        if line.startswith('DATABASE_URL='):
            db_url = line.strip().split('=', 1)[1]

if db_url.startswith("postgres://"):
    db_url = db_url.replace("postgres://", "postgresql://", 1)

try:
    engine = create_engine(db_url)
    with engine.connect() as conn:
        result = conn.execute(text("SELECT count(*) FROM events"))
        count = result.scalar()
        print(f"Connection Successful! Events table has {count} rows.")
except Exception as e:
    print(f"Connection Failed: {e}")
