#!/usr/bin/env python3
"""
Migrate Kuzu database to RyuGraph (OPTIONAL).

⚠️ NOTE: This script is OPTIONAL. If you're using mem0's 'kuzu' provider, it automatically
uses RyuGraph internally - no migration required. Your existing code continues to work.

This script is provided for users who want to:
1. Explicitly update their configs from 'provider: kuzu' to 'provider: ryu'
2. Understand the migration process
3. Migrate standalone Kuzu databases not managed by mem0

The migration primarily involves copying the database file and verifying the data can be
accessed with the new RyuGraph package, since RyuGraph is a fork of Kuzu with API compatibility.

Usage:
    python migrate_kuzu_to_ryu.py <kuzu_db_path> <ryu_db_path>

Example:
    python migrate_kuzu_to_ryu.py ./data/kuzu_db ./data/ryu_db

Requirements:
    - Both kuzu and ryugraph packages must be installed
    - pip install kuzu ryugraph
"""

import argparse
import sys
import shutil
from pathlib import Path
from typing import Dict, List, Any

try:
    import kuzu
except ImportError:
    print("Error: kuzu package not found. Please install it: pip install kuzu")
    sys.exit(1)

try:
    import ryu
except ImportError:
    print("Error: ryu package not found. Please install it: pip install ryugraph")
    sys.exit(1)


class KuzuToRyuMigrator:
    """Migrates Kuzu database to RyuGraph format."""

    def __init__(self, kuzu_db_path: str, ryu_db_path: str):
        """
        Initialize the migrator.

        Args:
            kuzu_db_path: Path to the source Kuzu database
            ryu_db_path: Path to the destination RyuGraph database
        """
        self.kuzu_db_path = Path(kuzu_db_path)
        self.ryu_db_path = Path(ryu_db_path)

    def validate_paths(self) -> bool:
        """
        Validate source and destination paths.

        Returns:
            bool: True if paths are valid
        """
        # Check if source exists
        if not self.kuzu_db_path.exists():
            print(f"Error: Source Kuzu database not found at {self.kuzu_db_path}")
            return False

        # Check if source is a directory
        if not self.kuzu_db_path.is_dir():
            print(f"Error: Source path {self.kuzu_db_path} is not a directory")
            return False

        # Check if destination already exists
        if self.ryu_db_path.exists():
            response = input(f"Warning: Destination {self.ryu_db_path} already exists. Overwrite? (yes/no): ")
            if response.lower() != 'yes':
                print("Migration cancelled.")
                return False
            shutil.rmtree(self.ryu_db_path)

        return True

    def export_kuzu_data(self) -> Dict[str, Any]:
        """
        Export all data from Kuzu database.

        Returns:
            dict: Exported data containing nodes and relationships
        """
        print(f"Reading data from Kuzu database at {self.kuzu_db_path}...")

        try:
            db = kuzu.Database(str(self.kuzu_db_path))
            conn = kuzu.Connection(db)

            # Get all nodes
            print("  Exporting Entity nodes...")
            nodes_query = """
            MATCH (n:Entity)
            RETURN
                id(n) as id,
                n.user_id as user_id,
                n.agent_id as agent_id,
                n.run_id as run_id,
                n.name as name,
                n.mentions as mentions,
                n.created as created,
                n.embedding as embedding
            """
            nodes_result = conn.execute(nodes_query)
            nodes = list(nodes_result.rows_as_dict())
            print(f"  Found {len(nodes)} nodes")

            # Get all relationships
            print("  Exporting CONNECTED_TO relationships...")
            rels_query = """
            MATCH (src:Entity)-[r:CONNECTED_TO]->(dst:Entity)
            RETURN
                src.name as source_name,
                src.user_id as user_id,
                src.agent_id as agent_id,
                src.run_id as run_id,
                r.name as relationship_name,
                r.mentions as mentions,
                r.created as created,
                r.updated as updated,
                dst.name as destination_name
            """
            rels_result = conn.execute(rels_query)
            relationships = list(rels_result.rows_as_dict())
            print(f"  Found {len(relationships)} relationships")

            return {
                "nodes": nodes,
                "relationships": relationships,
                "schema": {
                    "node_table": "Entity",
                    "rel_table": "CONNECTED_TO"
                }
            }

        except Exception as e:
            print(f"Error reading from Kuzu database: {e}")
            raise

    def import_to_ryu(self, data: Dict[str, Any]) -> bool:
        """
        Import data into RyuGraph database.

        Args:
            data: Exported data from Kuzu

        Returns:
            bool: True if import successful
        """
        print(f"\nCreating RyuGraph database at {self.ryu_db_path}...")

        try:
            # Create RyuGraph database
            db = ryu.Database(str(self.ryu_db_path))
            conn = ryu.Connection(db)

            # Create schema
            print("  Creating schema...")
            conn.execute("""
                CREATE NODE TABLE IF NOT EXISTS Entity(
                    id SERIAL PRIMARY KEY,
                    user_id STRING,
                    agent_id STRING,
                    run_id STRING,
                    name STRING,
                    mentions INT64,
                    created TIMESTAMP,
                    embedding FLOAT[]);
            """)

            conn.execute("""
                CREATE REL TABLE IF NOT EXISTS CONNECTED_TO(
                    FROM Entity TO Entity,
                    name STRING,
                    mentions INT64,
                    created TIMESTAMP,
                    updated TIMESTAMP
                );
            """)

            # Import nodes
            print(f"  Importing {len(data['nodes'])} nodes...")
            nodes_imported = 0
            for node in data['nodes']:
                try:
                    # Build dynamic query based on available fields
                    fields = []
                    values = {}

                    if node.get('name'):
                        fields.append("name: $name")
                        values['name'] = node['name']
                    if node.get('user_id'):
                        fields.append("user_id: $user_id")
                        values['user_id'] = node['user_id']
                    if node.get('agent_id'):
                        fields.append("agent_id: $agent_id")
                        values['agent_id'] = node['agent_id']
                    if node.get('run_id'):
                        fields.append("run_id: $run_id")
                        values['run_id'] = node['run_id']

                    fields_str = ", ".join(fields)

                    query = f"""
                    MERGE (n:Entity {{{fields_str}}})
                    ON CREATE SET
                        n.mentions = $mentions,
                        n.created = $created,
                        n.embedding = $embedding
                    """

                    values['mentions'] = node.get('mentions', 1)
                    values['created'] = node.get('created')
                    values['embedding'] = node.get('embedding')

                    conn.execute(query, values)
                    nodes_imported += 1

                    if nodes_imported % 100 == 0:
                        print(f"    Imported {nodes_imported}/{len(data['nodes'])} nodes...")

                except Exception as e:
                    print(f"  Warning: Failed to import node {node.get('name', 'unknown')}: {e}")
                    continue

            print(f"  Successfully imported {nodes_imported} nodes")

            # Import relationships
            print(f"  Importing {len(data['relationships'])} relationships...")
            rels_imported = 0
            for rel in data['relationships']:
                try:
                    # Build match conditions
                    src_conditions = ["name: $source_name"]
                    dst_conditions = ["name: $dest_name"]
                    params = {
                        'source_name': rel['source_name'],
                        'dest_name': rel['destination_name'],
                        'relationship_name': rel['relationship_name'],
                        'mentions': rel.get('mentions', 1),
                        'created': rel.get('created'),
                        'updated': rel.get('updated')
                    }

                    if rel.get('user_id'):
                        src_conditions.append("user_id: $user_id")
                        dst_conditions.append("user_id: $user_id")
                        params['user_id'] = rel['user_id']
                    if rel.get('agent_id'):
                        src_conditions.append("agent_id: $agent_id")
                        dst_conditions.append("agent_id: $agent_id")
                        params['agent_id'] = rel['agent_id']
                    if rel.get('run_id'):
                        src_conditions.append("run_id: $run_id")
                        dst_conditions.append("run_id: $run_id")
                        params['run_id'] = rel['run_id']

                    src_cond_str = ", ".join(src_conditions)
                    dst_cond_str = ", ".join(dst_conditions)

                    query = f"""
                    MATCH (src:Entity {{{src_cond_str}}})
                    MATCH (dst:Entity {{{dst_cond_str}}})
                    MERGE (src)-[r:CONNECTED_TO {{name: $relationship_name}}]->(dst)
                    ON CREATE SET
                        r.mentions = $mentions,
                        r.created = $created,
                        r.updated = $updated
                    """

                    conn.execute(query, params)
                    rels_imported += 1

                    if rels_imported % 100 == 0:
                        print(f"    Imported {rels_imported}/{len(data['relationships'])} relationships...")

                except Exception as e:
                    print(f"  Warning: Failed to import relationship: {e}")
                    continue

            print(f"  Successfully imported {rels_imported} relationships")

            return True

        except Exception as e:
            print(f"Error importing to RyuGraph database: {e}")
            raise

    def verify_migration(self) -> bool:
        """
        Verify the migration by comparing counts.

        Returns:
            bool: True if verification successful
        """
        print("\nVerifying migration...")

        try:
            # Open Kuzu database
            kuzu_db = kuzu.Database(str(self.kuzu_db_path))
            kuzu_conn = kuzu.Connection(kuzu_db)

            # Open RyuGraph database
            ryu_db = ryu.Database(str(self.ryu_db_path))
            ryu_conn = ryu.Connection(ryu_db)

            # Count nodes
            kuzu_nodes = kuzu_conn.execute("MATCH (n:Entity) RETURN COUNT(n) as count")
            kuzu_node_count = list(kuzu_nodes.rows_as_dict())[0]['count']

            ryu_nodes = ryu_conn.execute("MATCH (n:Entity) RETURN COUNT(n) as count")
            ryu_node_count = list(ryu_nodes.rows_as_dict())[0]['count']

            # Count relationships
            kuzu_rels = kuzu_conn.execute("MATCH ()-[r:CONNECTED_TO]->() RETURN COUNT(r) as count")
            kuzu_rel_count = list(kuzu_rels.rows_as_dict())[0]['count']

            ryu_rels = ryu_conn.execute("MATCH ()-[r:CONNECTED_TO]->() RETURN COUNT(r) as count")
            ryu_rel_count = list(ryu_rels.rows_as_dict())[0]['count']

            print(f"  Kuzu nodes: {kuzu_node_count}, RyuGraph nodes: {ryu_node_count}")
            print(f"  Kuzu relationships: {kuzu_rel_count}, RyuGraph relationships: {ryu_rel_count}")

            if kuzu_node_count == ryu_node_count and kuzu_rel_count == ryu_rel_count:
                print("  ✓ Verification successful! Counts match.")
                return True
            else:
                print("  ✗ Verification failed! Counts do not match.")
                return False

        except Exception as e:
            print(f"Error during verification: {e}")
            return False

    def migrate(self) -> bool:
        """
        Perform the complete migration.

        Returns:
            bool: True if migration successful
        """
        print("=" * 70)
        print("Kuzu to RyuGraph Migration Tool")
        print("=" * 70)

        # Validate paths
        if not self.validate_paths():
            return False

        # Export from Kuzu
        try:
            data = self.export_kuzu_data()
        except Exception as e:
            print(f"\nMigration failed during export: {e}")
            return False

        # Import to RyuGraph
        try:
            self.import_to_ryu(data)
        except Exception as e:
            print(f"\nMigration failed during import: {e}")
            return False

        # Verify migration
        if not self.verify_migration():
            print("\nMigration completed with warnings. Please verify your data manually.")
            return False

        print("\n" + "=" * 70)
        print("Migration completed successfully!")
        print("=" * 70)
        print(f"\nYour RyuGraph database is ready at: {self.ryu_db_path}")
        print("\nNext steps:")
        print("1. Update your mem0 configuration to use provider: 'ryu'")
        print("2. Update the database path in your configuration")
        print("3. Test your application with the new RyuGraph database")
        print("\nNote: You can safely delete the old Kuzu database after verifying")
        print("      everything works correctly with RyuGraph.")

        return True


def main():
    """Main entry point for the migration script."""
    parser = argparse.ArgumentParser(
        description="Migrate Kuzu database to RyuGraph",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Migrate from ./kuzu_db to ./ryu_db
  python migrate_kuzu_to_ryu.py ./kuzu_db ./ryu_db

  # Migrate from absolute paths
  python migrate_kuzu_to_ryu.py /path/to/kuzu_db /path/to/ryu_db

Requirements:
  Both kuzu and ryugraph packages must be installed:
    pip install kuzu ryugraph
        """
    )

    parser.add_argument(
        "kuzu_db_path",
        help="Path to the source Kuzu database directory"
    )
    parser.add_argument(
        "ryu_db_path",
        help="Path to the destination RyuGraph database directory"
    )

    args = parser.parse_args()

    # Create migrator and run
    migrator = KuzuToRyuMigrator(args.kuzu_db_path, args.ryu_db_path)
    success = migrator.migrate()

    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
