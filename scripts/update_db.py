from src.core import sqlite_db

def run():
    try:
        conn = sqlite_db.get_connection()
        cur = conn.cursor()
        cur.execute("UPDATE cameras SET source = '0', type = 'webcam', is_active = 1")
        conn.commit()
        conn.close()
        print('Updated cameras in SQL DB')
    except Exception as e:
        print(f"Error updating DB: {e}")

if __name__ == "__main__":
    run()
