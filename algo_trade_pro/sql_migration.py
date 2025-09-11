# Create and run: add_columns_migration.py
import sqlite3

def add_new_columns():
    conn = sqlite3.connect('algo_trade.db')
    cursor = conn.cursor()
    
    try:
        #cursor.execute('ALTER TABLE trades ADD COLUMN pending_sl_target FLOAT DEFAULT NULL')
        cursor.execute('ALTER TABLE trades ADD COLUMN underlying_symbol VARCHAR(20) DEFAULT NULL')
        conn.commit()
        print("Columns added successfully!")
    except sqlite3.OperationalError as e:
        print(f"Column may already exist: {e}")
    finally:
        conn.close()

if __name__ == "__main__":
    add_new_columns()
