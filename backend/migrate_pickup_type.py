import os
import sys
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from dotenv import load_dotenv

# Add backend to sys.path
sys.path.append(os.path.join(os.getcwd(), 'backend'))
from models import SessionLocal

load_dotenv('backend/.env')

def migrate():
    engine = SessionLocal().get_bind()
    with engine.connect() as conn:
        print("Adding pickup_type column to events table...")
        try:
            conn.execute(text("ALTER TABLE events ADD COLUMN pickup_type TEXT"))
            conn.commit()
            print("Column added successfully.")
        except Exception as e:
            print(f"Error adding column (it might already exist): {e}")
            conn.rollback()

if __name__ == "__main__":
    migrate()
