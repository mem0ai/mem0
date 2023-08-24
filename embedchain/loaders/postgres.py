import csv
import os
import re
import tempfile

from dotenv import load_dotenv

from embedchain.loaders.base_loader import BaseLoader
from embedchain.loaders.csv import CsvLoader

try:
    import psycopg2
except ImportError:
    raise ImportError("Postgres requires extra dependencies. Install with `pip install embedchain[postgres]`") from None


class PostgresLoader(BaseLoader):
    def __init__(self, *args, **kwargs):
        # Load environment variables from .env file for connection details
        load_dotenv()

        # Get connection details from environment variables
        connection_details = {
            "host": os.getenv("DB_HOST"),
            "port": int(os.getenv("DB_PORT")),
            "user": os.getenv("DB_USER"),
            "password": os.getenv("DB_PASSWORD"),
            "dbname": os.getenv("DB_NAME"),
        }

        # Establish connection to the PostgreSQL database
        self.conn = psycopg2.connect(**connection_details)

        # Call the base class's __init__ method with all args and kwargs
        super().__init__(*args, **kwargs)

    def _get_db_name(self):
        """Extract the database name from the connection's DSN."""
        # Use regex to find the database name within the connection DSN
        match = re.search(r"dbname=([a-zA-Z0-9_]+)", self.conn.dsn)
        return match.group(1) if match else None

    def load_data(self, content):
        """Load data from a PostgreSQL database using a query, write to a temporary CSV, and return the CSV content."""
        query = content
        # Execute query and fetch results
        with self.conn.cursor() as cursor:
            cursor.execute(query)
            rows = cursor.fetchall()
            column_names = [desc[0] for desc in cursor.description]

            # Write query results to a temporary CSV file
            with tempfile.NamedTemporaryFile(mode="w+", delete=False, suffix=".csv", newline="") as temp_file:
                csv_writer = csv.writer(temp_file)
                csv_writer.writerow(column_names)
                for row in rows:
                    csv_writer.writerow(row)
                temp_file_path = temp_file.name

        # Use CsvLoader to process the temporary CSV file
        output = CsvLoader.load_data(temp_file_path)

        # Overwrite metadata with query and database information
        for doc in output:
            doc["meta_data"]["url"] = query
            doc["meta_data"]["database"] = self._get_db_name()

        # Delete the temporary file when done
        os.remove(temp_file_path)

        return output

    def __del__(self):
        # Close the connection to the database when the object is destroyed
        self.conn.close()
