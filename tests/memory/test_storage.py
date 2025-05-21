import unittest
import os
import sqlite3
import tempfile
from mem0.memory.storage import SQLiteManager
import datetime # Required for creating datetime objects for created_at/updated_at

class TestSQLiteManager(unittest.TestCase):

    def setUp(self):
        # Create a temporary file for the database
        self.temp_db_file = tempfile.NamedTemporaryFile(delete=False, suffix=".sqlite")
        self.db_path = self.temp_db_file.name
        self.temp_db_file.close() # Close the file so SQLiteManager can open it

    def tearDown(self):
        # Ensure the connection is closed if possible (though SQLiteManager doesn't expose close directly)
        # and delete the temporary database file
        if hasattr(self, 'db_manager') and hasattr(self.db_manager, 'connection'):
            try:
                self.db_manager.connection.close()
            except sqlite3.ProgrammingError: # It might already be closed
                pass
        
        if hasattr(self, 'in_memory_manager') and hasattr(self.in_memory_manager, 'connection'):
             try:
                self.in_memory_manager.connection.close()
             except sqlite3.ProgrammingError:
                pass

        if os.path.exists(self.db_path):
            os.remove(self.db_path)

    def test_local_db_creation_and_interaction(self):
        # Ensure file does not exist (setUp should handle initial state, but double check)
        if os.path.exists(self.db_path):
            os.remove(self.db_path) 
            # Re-create it for the test after ensuring it's gone
            # This is a bit redundant if setUp properly creates a unique new file each time
            # but good for safety if db_path was a fixed name.
            # Given NamedTemporaryFile, this is less of an issue.
            
        self.assertFalse(os.path.exists(self.db_path), "Database file should not exist before instantiation for this test logic")

        # Instantiate SQLiteManager with the file path
        self.db_manager = SQLiteManager(db_path=self.db_path)
        
        # Verify that the database file is created
        self.assertTrue(os.path.exists(self.db_path), "Database file was not created at the specified path.")

        # Perform basic database operations
        memory_id = "test_memory_local_1"
        old_memory = "old local memory content"
        new_memory = "new local memory content"
        event = "local_test_event"
        # ASIF: SQLiteManager.add_history expects datetime objects for created_at and updated_at.
        # If None, the underlying SQL INSERT might fail or use defaults if the table is configured for it.
        # The existing add_history in storage.py does not seem to auto-generate these if None.
        # The table schema has DATETIME for these, so providing them.
        now = datetime.datetime.now()

        self.db_manager.add_history(
            memory_id=memory_id,
            old_memory=old_memory,
            new_memory=new_memory,
            event=event,
            created_at=now,
            updated_at=now,
            is_deleted=0
        )

        # Retrieve and verify history
        history = self.db_manager.get_history(memory_id)
        self.assertEqual(len(history), 1, "Should retrieve one history entry.")
        entry = history[0]
        self.assertEqual(entry["memory_id"], memory_id)
        self.assertEqual(entry["old_memory"], old_memory)
        self.assertEqual(entry["new_memory"], new_memory)
        self.assertEqual(entry["event"], event)
        # ASIF: Timestamps might be strings from the DB, compare accordingly or parse.
        # The get_history method returns them as they are fetched.
        # Assuming they are returned as strings in the format they were inserted or default SQLite format.
        # For simplicity, just checking they exist. More robust check would parse and compare datetime objects.
        self.assertIsNotNone(entry["created_at"])
        self.assertIsNotNone(entry["updated_at"])
        
        # Test that the connection is indeed to the file by trying to open it directly
        conn_direct = sqlite3.connect(self.db_path)
        cursor = conn_direct.cursor()
        cursor.execute("SELECT COUNT(*) FROM history WHERE memory_id = ?", (memory_id,))
        count = cursor.fetchone()[0]
        self.assertEqual(count, 1, "Direct check of DB file did not find the record.")
        conn_direct.close()


    def test_in_memory_db(self):
        # Instantiate SQLiteManager without a db_path argument (or with ":memory:")
        self.in_memory_manager = SQLiteManager() # Defaults to :memory:

        # Perform basic database operations
        memory_id = "test_memory_in_mem_1"
        old_memory = "old in-memory content"
        new_memory = "new in-memory content"
        event = "in_memory_test_event"
        now = datetime.datetime.now()

        self.in_memory_manager.add_history(
            memory_id=memory_id,
            old_memory=old_memory,
            new_memory=new_memory,
            event=event,
            created_at=now,
            updated_at=now,
            is_deleted=0
        )

        # Retrieve and verify history
        history = self.in_memory_manager.get_history(memory_id)
        self.assertEqual(len(history), 1, "Should retrieve one history entry for in-memory DB.")
        entry = history[0]
        self.assertEqual(entry["memory_id"], memory_id)
        self.assertEqual(entry["old_memory"], old_memory)
        self.assertEqual(entry["new_memory"], new_memory)
        self.assertEqual(entry["event"], event)
        self.assertIsNotNone(entry["created_at"])
        self.assertIsNotNone(entry["updated_at"])

        # Ensure this test doesn't create a file named ":memory:"
        self.assertFalse(os.path.exists(":memory:"), "An actual file named ':memory:' should not be created.")

if __name__ == '__main__':
    unittest.main()
