import os
import psycopg2
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)
if "?pgbouncer=" in DATABASE_URL:
    DATABASE_URL = DATABASE_URL.split("?")[0]

def create_rpc():
    conn = psycopg2.connect(DATABASE_URL)
    cur = conn.cursor()
    
    try:
        # Create RPC function to handle bookmark count
        print("Creating handle_bookmark_count RPC function...")
        sql = """
        CREATE OR REPLACE FUNCTION handle_bookmark_count(p_event_id INT, p_increment INT)
        RETURNS VOID AS $$
        BEGIN
            UPDATE events
            SET bookmark_count = GREATEST(0, bookmark_count + p_increment)
            WHERE id = p_event_id;
        END;
        $$ LANGUAGE plpgsql;
        """
        cur.execute(sql)
        conn.commit()
        print("RPC function created successfully.")
    except Exception as e:
        print(f"Failed to create RPC: {e}")
        conn.rollback()
    finally:
        cur.close()
        conn.close()

if __name__ == "__main__":
    create_rpc()
