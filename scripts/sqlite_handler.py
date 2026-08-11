import datetime
import logging
import sqlite3
from sqlite3 import Error
import json
from pathlib import Path
from sys import exception
from typing import Any
from xmlrpc.client import boolean

class SQLiteHandler:
    def __init__(self, logger: logging.Logger, db_path: str) -> None:
        self.logger = logger
        self.db_path = db_path
        self.lookup_tables = {}

        # Get parent folder of the db_path and create it if it doesn't exist
        db_folder = Path(db_path).parent
        db_folder.mkdir(parents=True, exist_ok=True)

        self.connection = sqlite3.connect(db_path)
        self.cursor = self.connection.cursor()

    def close(self):
        if self.connection:
            self.connection.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

    def create_schema(self):
        """
        Create the database schema if it doesn't exist
        """

        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS schema_version (
                version TEXT PRIMARY KEY,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
            """
        )

        """
        The extended properties of a monitor are store in column config
        It's main purpose is to make the database schema future proof.
        More functions can be added like running a command.
        For example:
        config = {
            {"monitor_period": "10m"},
            "command": "python restore_db.py",
            "retries": 3,
            }
        """
        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS monitors (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                monitor_path TEXT NOT NULL,
                remote_path TEXT,
                monitor_type TEXT NOT NULL,
                config JSON, -- Contains JSON for monitor-specific settings
                status TEXT,
                last_run DATETIME,
                last_heartbeat DATETIME,
                last_modified DATETIME DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
                
        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS profiles (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                profile_type TEXT NOT NULL,
                config JSON, -- Contains JSON for profile-specific settings (e.g., credentials)
                date_created DATETIME DEFAULT CURRENT_TIMESTAMP,
                last_modified DATETIME DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
                
        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS providers (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE,
                profile_type TEXT NOT NULL,
                description TEXT,
                config TEXT, -- Contains JSON for provider-specific settings
                date_created DATETIME DEFAULT CURRENT_TIMESTAMP,
                last_modified DATETIME DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
                
        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS lookup_tables (
                table_name TEXT PRIMARY KEY,
                config TEXT, -- Contains JSON for lookup table.
                last_modified DATETIME DEFAULT CURRENT_TIMESTAMP
            )
            """
        )

        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS monitor_profile_map (
                monitor_id INTEGER NOT NULL,
                profile_id INTEGER NOT NULL,
                PRIMARY KEY (monitor_id, profile_id),
                FOREIGN KEY (monitor_id) REFERENCES monitors (id),
                FOREIGN KEY (profile_id) REFERENCES profiles (id)
            )
            """
        )

        self.connection.commit()
        self.load_support_tables()

    def load_support_tables(self):
        """
        Create support tables
        Support tables will remain unchanged most of the time.
        Their function is ususally to lookup values like monitor_type, folder_type etc.
        """

        # Add lookup tables to database
        # Lookup tables are stored in JSON format to allow for easy extending the database without changing the database structure
        # Lookup tables are basically virtual tables
        table_name = "monitor_statuses"
        config = [
                {"name": "running", "description": "Monitor is running", "implemented": "true"},
                {"name": "stop", "description": "Monitor is about to stop", "implemented": "true"},
                {"name": "stopped", "description": "Monitor has stopped running", "implemented": "true"},
                {"name": "error", "description": "Monitor has an error state", "implemented": "true"},
            ]

        try:
            self.update_lookup_table(
                table_name=table_name,
                config=config
                )
            self.logger.info(f"Lookup table {table_name} updated or added successfully")
        except Exception as e:
            self.logger.error(f"Error adding lookup table: {e}")
        
        table_name = "monitor_types"
        config = [
                {"name": "instant-upload", "description": "Instant upload to remote", "implemented": "true"},
                {"name": "periodic_upload", "description": "Periodic upload to remote", "implemented": "true"},
                {"name": "periodic_download", "description": "Periodic download from remote", "implemented": "true"},
                {"name": "run_command", "description": "Run a command", "implemented": "true"},
            ]

        try:
            self.update_lookup_table(
                table_name=table_name,
                config=config
                )
            self.logger.info(f"Lookup table {table_name} updated or added successfully")
        except Exception as e:
            self.logger.error(f"Error adding lookup table: {e}")

        # Add profile types to database
        # Profile types can be extended with more profile types during profile import
        table_name = "profile_types"
        config = [
                {"name": "s3", "description": "S3 compatible cloud storage, like AWS S2, Cloudflare R2, Backblaze B2 etc", "implemented": "true"},
                {"name": "drive", "description": "Google Drive", "implemented": "false"},
                {"name": "azure", "description": "Azure Blob Storage", "implemented": "false"},
                {"name": "ftp", "description": "FTP Server", "implemented": "false"},
                {"name" : "sftp", "description": "SFTP Server", "implemented": "false"},
                {"name" : "ssh", "description": "SSH Server", "implemented": "false"},
                {"name" : "http", "description": "HTTP Server", "implemented": "false"},
            ]

        try:
            self.update_lookup_table(
                table_name=table_name,
                config=config
                )
            self.logger.info(f"Lookup table {table_name} updated or added successfully")
        except Exception as e:
            self.logger.error(f"Error adding lookup table {table_name}: {e}")

        # Add providers to database
        # More providers can be added during profile import
        providers = [
            {
                "name": "Amazon AWS S3",
                "profile_type": "s3",
                "description": "Amazon AWS S3",
                "config": {}
            },
            {
                "name": "Cloudflare",
                "profile_type": "s3",
                "description": "Cloudflare R2 - S3 compatible cloud storage",
                "config": {}
            },
            {
                "name": "IDrive",
                "profile_type": "s3",
                "description": "Idrive E2 - S3 compatible cloud storage",
                "config": {}
            },
            {
                "name": "Backblaze",
                "profile_type": "s3",
                "description": "Backblaze B2 - S3 compatible cloud storage",
                "config": {}
            },
            {
                "name": "Other",
                "profile_type": "s3",
                "description": "Other S3 compatible cloud storage",
                "config": {}
            },
        ]

        for provider in providers:
            self.logger.debug(f"Adding provider: {provider['name']}")
            # Add provider to database
            self.add_provider(
                name=provider["name"],
                profile_type=provider["profile_type"],
                description=provider["description"],
                config=provider["config"]
            )
        
        self.connection.commit()


    def is_profle_type_implemented(self, profile_type: str) -> bool:
        """
        Check if a profile type is implemented
        """

        implemented_profile_types = self.get_implemented_profile_types()
        for implemented_profile_type in implemented_profile_types:
            if implemented_profile_type["name"] == profile_type:
                return True
        return False

    def get_implemented_profile_types(self) -> list[dict[str, Any]]:
        """
        Convenience method to get all implemented profile types
        """
        profile_types = self.get_lookup_table(table_name="profile_types")
        if profile_types is None:
            return []
        implemented_profile_types = []
        for profile_type in profile_types:
            if profile_type.get("implemented", "false").lower() == "true":
                implemented_profile_types.append(profile_type)
        return implemented_profile_types

    def get_implemented_profiles(self) -> list[dict[str, Any]]:
        """
        Get all profiles with a profile_type that has been implemented
        """

        profile_types = self.get_lookup_table(table_name="profile_types")
        if profile_types is None:
            return []

        # Get all profiles that have been implemented yet
        implemented_profiles : list[dict[str, Any]] = []
        profiles = self.get_profiles()
        if profiles is None or len(profiles) == 0:
            return []

        for profile in profiles:
            profile_profile_type = profile.get("profile_type", "")
            for profile_type in profile_types:
                if profile_type.get("name", "") != profile_profile_type:
                    continue
                if profile_type.get("implemented", "false").lower() == "false":
                    continue
                implemented_profiles.append(profile)

        return implemented_profiles


    def get_implemented_providers(self) -> list[dict[str, Any]]:
        """
        Get all providers with a profile_type that has been implemented
        """
        
        # Get profile types from lookup tables
        profile_types = self.get_lookup_table(table_name="profile_types")
        if profile_types is None:
            print(f"No profile types found in lookup tables in {self.db_path}")
            return []

        # Get all providers that have been implemented yet
        providers = self.get_providers()
        if providers is None or len(providers) == 0:
            print(f"No providers found in {self.db_path}")
            return []

        implemented_providers : list[dict] = []
        for provider in providers:
            provider_profile_type = provider.get("profile_type", "")
            # Filter providers that have a provider type that is implemented
            for profile_type in profile_types:
                if profile_type is None:
                    continue
                if provider_profile_type is None:
                    continue
                profile_type_name = profile_type.get("name", "")
                if profile_type_name != provider_profile_type:
                    continue
                implemented = profile_type.get("implemented", "false").lower() == "true"
                if not implemented:
                    continue
                # This profile_type is implemented
                implemented_providers.append(provider)
        return implemented_providers


    def update_schema_version(self, version: str):
        """
        Update the schema version in the database
        """
        self.cursor.execute("INSERT OR REPLACE INTO schema_version (version) VALUES (:version)", {"version": version})
        self.connection.commit()

    def get_current_schema_version(self) -> str:
        """
            Get the current schema version from the database
            The current schema version is the one with the highest version value in the schema_version table
        """ 
        self.cursor.execute("SELECT version FROM schema_version ORDER BY version DESC LIMIT 1")
        result = self.cursor.fetchone()
        return result[0] if result else ""
    
    def get_schema_versions(self) -> list[dict[str, datetime.datetime]]:
        """
        Return all schema versions in ascending order of version.
        Each entry is a dictionary with keys 'version' and 'updated_at'.
        """
        self.cursor.execute("""
            SELECT version, updated_at
            FROM schema_version
            ORDER BY version ASC
        """)
        rows = self.cursor.fetchall()
        return [
            {"version": row[0], "updated_at": row[1]}
            for row in rows
        ]

    def get_lookup_table(self, table_name: str) -> list[dict[str, Any]]:
        """
        Get lookup tables config from database or memory cache if it exists. 
        Lookup tables are stored in JSON format in the database to allow for easy extending the database without changing the database structure. 
        Lookup tables are basically virtual tables.
        """

        if table_name not in self.lookup_tables.keys():
            self.cursor.execute("SELECT * FROM lookup_tables WHERE table_name = :table_name", 
                {"table_name": table_name}
                )
            row = self.cursor.fetchone()
            if not row:
                self.logger.debug(f"Lookup table {table_name} found in {self.db_path}")
                return []
            # lookup_table is a dictionary with key table_name
            lookup_table = json.loads(row[1]) if row[1] else {}
            self.lookup_tables[table_name] = lookup_table.get(table_name, [])

        return self.lookup_tables.get(table_name, [])

    def update_lookup_table(self, table_name: str, config: list[dict[str, Any]]) -> int | None:
        """
        The lookup_tables table is used to store the configuration of virtual tables like monitor_type.
        This avoids hard coding values and makes it future proof.
        """

        config_dict = {table_name: config}
        config_str = json.dumps(config_dict)
        self.cursor.execute("""
            INSERT INTO lookup_tables (table_name, config)
            VALUES (:table_name, :config)
            ON CONFLICT(table_name) DO UPDATE SET config = :config
            """, 
            {"table_name": table_name, "config": config_str}
        )
        self.connection.commit()
        # lastrowid is unreliable with INSERT OR REPLACE / ON CONFLICT;
        # fetch the actual rowid via a separate query.
        self.cursor.execute(
            "SELECT rowid FROM lookup_tables WHERE table_name = :table_name",
            {"table_name": table_name}
        )
        row = self.cursor.fetchone()
        return row[0] if row else None
    
    def add_monitor(self, name: str, monitor_path: str, remote_path: str, monitor_type: str, config: dict, status: str) -> int | None:
        """
        Add a monitor to the database
        """

        config_str = json.dumps(config)
        self.cursor.execute("""
            INSERT INTO monitors (name, monitor_path, remote_path, monitor_type, config, status)
            VALUES (:name, :monitor_path, :remote_path, :monitor_type, :config, :status)
        """, {
            "name": name,
            "monitor_path": monitor_path,
            "remote_path": remote_path,
            "monitor_type": monitor_type,
            "config": config_str,
            "status": status
        })
        self.connection.commit()
        return self.cursor.lastrowid

    def update_monitor(self, monitor_id: int, name: str, monitor_path: str, remote_path: str, monitor_type: str, config: dict, status: str) -> int | None:
        """
        Update a monitor in the database
        """
        
        config_str = json.dumps(config)
        self.cursor.execute("""
            UPDATE monitors
            SET name = :name, 
                monitor_path = :monitor_path, 
                remote_path = :remote_path, 
                monitor_type = :monitor_type, 
                config = :config, 
                status = :status,
                last_modified = CURRENT_TIMESTAMP
            WHERE id = :id
        """, {
            "name": name,
            "monitor_path": monitor_path,
            "remote_path": remote_path,
            "monitor_type": monitor_type,
            "config": config_str,
            "status": status,
            "id": monitor_id
        })
        self.connection.commit()
        # UPDATE does not set lastrowid; return the known id instead.
        return monitor_id

    def get_monitor(self, monitor_id: int | None = None, monitor_name: str | None = None) -> dict:
        """
        Get a monitor from the database by id or name
        """
        if monitor_id is not None:
            self.cursor.execute("SELECT * FROM monitors WHERE id = :id", {"id": monitor_id})
        elif monitor_name is not None:
            self.cursor.execute("SELECT * FROM monitors WHERE name = :name", {"name": monitor_name})
        else:
            raise ValueError("Either monitor_id or monitor_name must be provided")

        row = self.cursor.fetchone()
        if row:
            return {
                "id": row[0],
                "name": row[1],
                "monitor_path": row[2],
                "remote_path": row[3],
                "monitor_type": row[4],
                "config": json.loads(row[5]) if row[5] else None,
                "status": row[6],
                "last_run": row[7],
                "last_heartbeat": row[8]
            }
        return {}
    
    def get_monitors(self) -> list[dict]:
        """
        Get all monitors from the database
        """
        self.cursor.execute("SELECT * FROM monitors")
        rows = self.cursor.fetchall()
        return [
            {
                "id": row[0],
                "name": row[1],
                "monitor_path": row[2],
                "remote_path": row[3],
                "monitor_type": row[4],
                "config": json.loads(row[5]) if row[5] else None,
                "status": row[6],
                "last_run": row[7],
                "last_heartbeat": row[8]
            }
            for row in rows
        ]
    
    def update_monitor_status(self, monitor_id: int, status: str):
        """
        Update the status of a monitor in the database
        """
        
        self.cursor.execute("UPDATE monitors SET status = :status , last_modified = CURRENT_TIMESTAMP WHERE id = :id", {
            "status": status, "id": monitor_id
        })
        self.connection.commit()

    def update_monitor_last_run(self, monitor_id: int, last_run: str):
        """
        Update the last run time of a monitor in the database
        """
        self.cursor.execute("UPDATE monitors SET last_run = :last_run WHERE id = :id", {
            "last_run": last_run, "id": monitor_id
        })
        self.connection.commit()

    def update_monitor_last_heartbeat(self, monitor_id: int, last_heartbeat: str):
        """
        Update the last heartbeat time of a monitor in the database
        """
        self.cursor.execute("UPDATE monitors SET last_heartbeat = :last_heartbeat WHERE id = :id", {
            "last_heartbeat": last_heartbeat, "id": monitor_id
        })
        self.connection.commit()

    def update_monitor_config(self, monitor_id: int, config: dict):
        """
        Update the config of a monitor in the database
        """
        
        config_str = json.dumps(config)
        self.cursor.execute("UPDATE monitors SET config = :config, last_modified = CURRENT_TIMESTAMP WHERE id = :id", {
            "config": config_str, "id": monitor_id
        })
        self.connection.commit()

    def delete_monitor(self, monitor_id: int) -> bool:
        """
        Delete a monitor from the database
        Also delete all entries in monitor_profile_map that reference this monitor to avoid orphaned entries
        """
        
        try:
            # Delete this monitor from monitor_profile_map first
            self.cursor.execute("DELETE FROM monitor_profile_map WHERE monitor_id = :id", {"id": monitor_id})
            self.cursor.execute("DELETE FROM monitors WHERE id = :id", {"id": monitor_id})
            self.connection.commit()
            return True
        except Exception as e:
            self.logger.error(f"Error occurred while deleting monitor: {e}")

        return False


    def add_profile(self, name: str, profile_type: str, config: dict) -> int | None:
        """
        Add a profile to the database
        """
        self.cursor.execute("""
            INSERT INTO profiles (
                name, 
                profile_type,
                config, 
                date_created, last_modified
            )
            VALUES (
                :name, :profile_type, :config, 
                CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
            )
        """, {
            "name": name,
            "profile_type": profile_type,
            "config": json.dumps(config)
        })
        self.connection.commit()
        return self.cursor.lastrowid    
    

    def get_profile(self, profile_id: int | None = None, profile_name: str | None = None) -> dict:
        """Get a profile from the database by id or name"""
        try:
            if profile_id is not None:
                self.cursor.execute("SELECT * FROM profiles WHERE id = :id", {"id": profile_id})
            elif profile_name is not None:
                self.cursor.execute("SELECT * FROM profiles WHERE name = :name", {"name": profile_name})
            else:
                raise ValueError("Either profile_id or profile_name must be provided")

            row = self.cursor.fetchone()
            if row:
                return {
                    "id": row[0],
                    "name": row[1],
                    "profile_type": row[2],
                    "config": json.loads(row[3]) if row[3] else None,
                    "date_created": row[4],
                    "last_modified": row[5]
                }
        except Exception as e:
            self.logger.error(f"Error occurred while fetching profile: {e}")
        return {}
    
    def update_profile(self, profile_id: int, name: str, profile_type: str, config: dict) -> int | None:
        """
        Update a profile in the database
        """

        self.cursor.execute("""
            UPDATE profiles
            SET name = :name, 
                profile_type = :profile_type, 
                config = :config, 
                last_modified = CURRENT_TIMESTAMP
            WHERE id = :id
        """, {
            "name": name,
            "profile_type": profile_type,
            "config": json.dumps(config),
            "id": profile_id
        })
        self.connection.commit()
        # UPDATE does not set lastrowid; return the known id instead.
        return profile_id


    def delete_profile(self, profile_id: int | None = None, profile_name: str | None = None) -> boolean:
        """
        Delete a profile from the database
        Also delete all entries in monitor_profile_map that reference this profile to avoid orphaned entries
        """
        
        try:
            # First delete this profile from monitor_profile_map
            if profile_id is not None:
                self.cursor.execute("DELETE FROM monitor_profile_map WHERE profile_id = :id", {"id": profile_id})
                self.cursor.execute("DELETE FROM profiles WHERE id = :id", {"id": profile_id})
            elif profile_name is not None:
                self.cursor.execute("DELETE FROM monitor_profile_map WHERE profile_id = (SELECT id FROM profiles WHERE name = :name)", {"name": profile_name})
                self.cursor.execute("DELETE FROM profiles WHERE name = :name", {"name": profile_name})
            self.connection.commit()
        except Exception as e:
            self.logger.error(f"Error: {e}")
            return False
     
        return True

    def get_profiles(self) -> list[dict[str, Any]]:
        """
        Get all profiles from the database
        """
        
        self.cursor.execute("SELECT * FROM profiles")
        rows = self.cursor.fetchall()
        return [
            {
                "id": row[0],
                "name": row[1],
                "profile_type": row[2],
                "config": json.loads(row[3]) if row[3] else None,
                "date_created": row[4],
                "last_modified": row[5]
            }
            for row in rows
        ]   
    
    def add_monitor_profile_map(self, monitor_id: int, profile_id: int):
        """
        Add a mapping between a monitor and a profile in the database
        """
        
        self.cursor.execute("""
            INSERT OR IGNORE INTO monitor_profile_map (monitor_id, profile_id)
            VALUES (:monitor_id, :profile_id)
        """, {"monitor_id": monitor_id, "profile_id": profile_id})
        self.connection.commit()

    def delete_monitor_profile_map(self, monitor_id: int, profile_id: int):
        """
        Delete a mapping between a monitor and a profile from the database
        """
        
        self.cursor.execute("""
            DELETE FROM monitor_profile_map
            WHERE monitor_id = :monitor_id AND profile_id = :profile_id
        """, {"monitor_id": monitor_id, "profile_id": profile_id})
        self.connection.commit()

    def get_profiles_for_monitor(self, monitor_id: int) -> list:
        """
        Get all profiles linked to a specific monitor from the database
        """
        
        self.cursor.execute("""
            SELECT p.*
            FROM profiles p
            JOIN monitor_profile_map mpm ON p.id = mpm.profile_id
            WHERE mpm.monitor_id = :monitor_id
        """, {"monitor_id": monitor_id})
        rows = self.cursor.fetchall()
        return [
            {
                "id": row[0],
                "name": row[1],
                "profile_type": row[2],
                "config": json.loads(row[3]) if row[3] else None,
                "date_created": row[4],
                "last_modified": row[5]
            }
            for row in rows
        ]   
    
    def get_monitors_for_profile(self, profile_id: int) -> list:
        """
        Get all monitors linked to a profile from the database
        """
        
        self.cursor.execute("""
            SELECT m.*
            FROM monitors m
            JOIN monitor_profile_map mpm ON m.id = mpm.monitor_id
            WHERE mpm.profile_id = :profile_id
        """, {"profile_id": profile_id})
        rows = self.cursor.fetchall()
        return [
            {
                "id": row[0],
                "name": row[1],
                "monitor_path": row[2],
                "remote_path": row[3],
                "monitor_type": row[4],
                "config": json.loads(row[5]) if row[5] else None,
                "status": row[6],
                "last_run": row[7],
                "last_heartbeat": row[8]
            }
            for row in rows
        ]

    def add_provider(self, name: str, profile_type: str, description: str, config: dict) -> int | None:
        """
        Add a provider to the database
        """
        
        self.cursor.execute("""
            INSERT OR REPLACE INTO providers (
                name, 
                profile_type,
                description,
                config, 
                date_created, last_modified
            )
            VALUES (
                :name, :profile_type, :description,
                :config, 
                CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
            )
        """, {
            "name": name,
            "profile_type": profile_type,
            "description": description,
            "config": json.dumps(config)
        })
        self.connection.commit()
        return self.cursor.lastrowid    
    
    def get_provider(self, provider_id: int | None = None, provider_name: str | None = None) -> dict:
        """
        Get a provider from the database by id or name
        """
        
        try:
            if provider_id is not None:
                self.cursor.execute("SELECT * FROM providers WHERE id = :id", {"id": provider_id})
            elif provider_name is not None:
                self.cursor.execute("SELECT * FROM providers WHERE name = :name", {"name": provider_name})
            else:
                raise ValueError("Either provider_id or provider_name must be provided")

            row = self.cursor.fetchone()
            if row:
                return {
                    "id": row[0],
                    "name": row[1],
                    "profile_type": row[2],
                    "description": row[3],
                    "config": json.loads(row[4]) if row[4] else None,
                    "date_created": row[5],
                    "last_modified": row[6]
                }
        except Exception as e:
            self.logger.error(f"Error occurred while fetching provider: {e}")
        return {}

    def update_provider(self, provider_id: int, name: str, profile_type: str, description: str, config: dict):
        """
        Update a provider in the database
        """
        
        self.cursor.execute("""
            UPDATE providers
            SET name = :name, 
                profile_type = :profile_type, 
                description = :description,
                config = :config, 
                last_modified = CURRENT_TIMESTAMP
            WHERE id = :id
        """, {
            "name": name,
            "profile_type": profile_type,
            "description": description,
            "config": json.dumps(config),
            "id": provider_id
        })
        self.connection.commit()

    def delete_provider(self, provider_id: int):
        """
        Delete a provider from the database
        """
        
        self.cursor.execute("DELETE FROM providers WHERE id = :id", {"id": provider_id})
        self.connection.commit()

    def get_providers(self) -> list[dict]:
        """
        Get all providers from the database
        """
        
        self.cursor.execute("SELECT * FROM providers")
        rows = self.cursor.fetchall()
        return [
            {
                "id": row[0],
                "name": row[1],
                "profile_type": row[2],
                "description": row[3],
                "config": json.loads(row[4]) if row[4] else None,
                "date_created": row[5],
                "last_modified": row[6]
            }
            for row in rows
        ]
    
    def __del__(self):
        self.close()

if __name__ == "__main__":
    pass
    # Example usage:
    # logger = logging.getLogger("SQLiteHandler")
    # sqlite_handler = SQLiteHandler(logger=logger, db_path="data/foldermonitor.sqlite")
    # sqlite_handler.create_schema()


    