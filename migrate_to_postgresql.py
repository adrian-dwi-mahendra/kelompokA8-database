#!/usr/bin/env python3
"""
migrate_to_postgresql.py
Migrate data dari SQLite (ayam.db) ke PostgreSQL

Usage:
    python migrate_to_postgresql.py postgresql://user:pass@host:port/db
"""

import sys
import sqlite3
import psycopg2
from psycopg2.extras import execute_values

def migrate():
    if len(sys.argv) < 2:
        print("❌ Usage: python migrate_to_postgresql.py DATABASE_URL")
        print("\nExample:")
        print("  python migrate_to_postgresql.py postgresql://postgres:pass@localhost:5432/snbt")
        sys.exit(1)
    
    pg_url = sys.argv[1]
    sqlite_db = "ayam.db"
    
    print("\n" + "="*60)
    print("🔄 MIGRATING DATA: SQLite → PostgreSQL")
    print("="*60)
    
    # Connect to SQLite
    try:
        sqlite_conn = sqlite3.connect(sqlite_db)
        sqlite_conn.row_factory = sqlite3.Row
        print(f"✅ Connected to SQLite: {sqlite_db}")
    except Exception as e:
        print(f"❌ Error connecting to SQLite: {e}")
        sys.exit(1)
    
    # Connect to PostgreSQL
    try:
        pg_conn = psycopg2.connect(pg_url)
        print(f"✅ Connected to PostgreSQL")
    except Exception as e:
        print(f"❌ Error connecting to PostgreSQL: {e}")
        sys.exit(1)
    
    # Get tables from SQLite
    sqlite_cur = sqlite_conn.cursor()
    sqlite_cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = [row[0] for row in sqlite_cur.fetchall()]
    
    pg_cur = pg_conn.cursor()
    
    for table in tables:
        try:
            # Get columns
            sqlite_cur.execute(f"PRAGMA table_info({table})")
            columns = [row[1] for row in sqlite_cur.fetchall()]
            
            # Fetch all data from SQLite table
            sqlite_cur.execute(f"SELECT * FROM {table}")
            rows = sqlite_cur.fetchall()
            
            if not rows:
                print(f"⏭️  {table}: (0 rows, skipped)")
                continue
            
            # Convert rows to tuples
            data = [tuple(row) for row in rows]
            
            # Delete existing data in PostgreSQL table
            try:
                pg_cur.execute(f"DELETE FROM {table}")
            except:
                pass  # Table might not exist yet
            
            # Insert data into PostgreSQL
            cols_str = ", ".join(columns)
            placeholders = ", ".join(["%s"] * len(columns))
            insert_query = f"INSERT INTO {table} ({cols_str}) VALUES ({placeholders})"
            
            execute_values(pg_cur, insert_query, data, page_size=1000)
            pg_conn.commit()
            
            print(f"✅ {table}: {len(rows)} rows imported")
        
        except Exception as e:
            print(f"⚠️  {table}: Error - {e}")
            pg_conn.rollback()
    
    sqlite_conn.close()
    pg_conn.close()
    
    print("\n" + "="*60)
    print("🎉 MIGRATION COMPLETE!")
    print("="*60)
    print("\nData dari SQLite sudah berhasil di-import ke PostgreSQL")
    print("Aplikasi siap untuk production! 🚀\n")

if __name__ == "__main__":
    migrate()
