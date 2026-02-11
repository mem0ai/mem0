import sqlite3

# Path to the database file you copied
db_file = "test_after.db"

def inspect_db():
    try:
        # Connect to the local SQLite file
        conn = sqlite3.connect(db_file)
        cursor = conn.cursor()

        # 1. List all tables in the database
        print("--- Tables in Database ---")
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = cursor.fetchall()
        if not tables:
            print("No tables found.")
            return
        
        for table in tables:
            table_name = table[0]
            print(f"\nTable: {table_name}")
            
            # 2. Get the schema/columns for each table
            cursor.execute(f"PRAGMA table_info('{table_name}');")
            columns = [col[1] for col in cursor.fetchall()]
            print(f"Columns: {', '.join(columns)}")

            # 3. Print the first 5 rows of data
            cursor.execute(f"SELECT * FROM {table_name} LIMIT 5;")
            rows = cursor.fetchall()
            if rows:
                print("Sample Data:")
                for row in rows:
                    print(row)
            else:
                print("Table is empty.")

        conn.close()
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    inspect_db()
