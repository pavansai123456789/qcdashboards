import psycopg2
from psycopg2 import OperationalError

def test_connection():
    try:
        conn = psycopg2.connect(
            host="10.21.137.79",
            port="5432",
            database="postgres",       # change to your DB name
            user="pavansaigeddam",
            password="Weld@123"
        )

        print("✅ Connection successful!")

        cur = conn.cursor()
        cur.execute("SELECT version();")
        print("PostgreSQL version:", cur.fetchone())

        cur.close()
        conn.close()
        print("🔌 Connection closed.")

    except OperationalError as e:
        print("❌ Connection failed!")
        print(e)

if __name__ == "__main__":
    test_connection()
