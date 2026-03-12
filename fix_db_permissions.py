import os
from sqlalchemy import create_engine, text

with open('backend/.env') as f:
    for line in f:
        if line.startswith('DATABASE_URL='):
            db_url = line.strip().split('=', 1)[1]

if db_url.startswith("postgres://"):
    db_url = db_url.replace("postgres://", "postgresql://", 1)

# Since we might not resolve the IPv6 host locally, we need to instruct the user to run it via GitHub,
# OR we can try to use the pooler URL instead?
