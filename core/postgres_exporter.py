"""PostgreSQL export for Gold layer analytics tables."""

import os
from pathlib import Path
from typing import Optional, Dict, List
import logging

import pandas as pd
from sqlalchemy import (
    create_engine,
    MetaData,
    Table,
    Column,
    String,
    Integer,
    Float,
    DateTime,
    Boolean,
    inspect,
    text,
)
from sqlalchemy.types import (
    VARCHAR,
    BIGINT,
    NUMERIC,
    TIMESTAMP,
    BOOLEAN,
)

from core.audit import AuditLogger


# ─── Configuration ──────────────────────────────────────────────────────────

ENABLE_POSTGRES = os.getenv("ENABLE_POSTGRES_EXPORT", "false").lower() == "true"

# Option 1: Direct DATABASE_URL
DATABASE_URL = os.getenv("DATABASE_URL", "")

# Option 2: Individual components
if not DATABASE_URL:
    POSTGRES_USER = os.getenv("POSTGRES_USER", "postgres")
    POSTGRES_PASSWORD = os.getenv("POSTGRES_PASSWORD", "")
    POSTGRES_HOST = os.getenv("POSTGRES_HOST", "localhost")
    POSTGRES_PORT = os.getenv("POSTGRES_PORT", "5432")
    POSTGRES_DATABASE = os.getenv("POSTGRES_DATABASE", "")
    
    if POSTGRES_DATABASE:
        DATABASE_URL = (
            f"postgresql://{POSTGRES_USER}:{POSTGRES_PASSWORD}@"
            f"{POSTGRES_HOST}:{POSTGRES_PORT}/{POSTGRES_DATABASE}"
        )

POSTGRES_SCHEMA = os.getenv("POSTGRES_SCHEMA", "public")
AUTO_CREATE_TABLES = os.getenv("POSTGRES_AUTO_CREATE_TABLES", "true").lower() == "true"
DROP_EXISTING = os.getenv("POSTGRES_DROP_EXISTING_TABLES", "false").lower() == "true"


# ─── PostgreSQL Exporter ────────────────────────────────────────────────────

class PostgreSQLExporter:
    """Export Gold layer Parquet files to PostgreSQL."""
    
    def __init__(self, run_id: str):
        """Initialize PostgreSQL exporter."""
        self.run_id = run_id
        self.logger = AuditLogger(run_id)
        self.engine = None
        self.connection_string = DATABASE_URL
    
    def connect(self) -> bool:
        """
        Establish connection to PostgreSQL.
        
        Returns:
            True if connection successful, False otherwise
        """
        if not ENABLE_POSTGRES:
            self.logger.log("postgres_exporter", "postgres_disabled")
            return False
        
        if not DATABASE_URL:
            self.logger.log(
                "postgres_exporter",
                "postgres_error",
                error="DATABASE_URL not configured in .env",
            )
            print("❌ PostgreSQL not configured. Set DATABASE_URL in .env")
            return False
        
        try:
            # Create engine with connection pooling
            self.engine = create_engine(
                DATABASE_URL,
                echo=False,
                pool_pre_ping=True,
                pool_size=10,
                max_overflow=20,
            )
            
            # Test connection
            with self.engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            
            self.logger.log("postgres_exporter", "connect_success")
            print("[OK] Connected to PostgreSQL")
            return True
        
        except Exception as e:
            error_msg = f"PostgreSQL connection failed: {e}"
            self.logger.log(
                "postgres_exporter",
                "connect_failed",
                error=str(e),
            )
            print(f"[ERROR] {error_msg}")
            return False
    
    def _get_sql_type(self, pandas_dtype: str) -> object:
        """Map pandas dtype to SQLAlchemy type."""
        dtype_str = str(pandas_dtype).lower()
        
        if "int" in dtype_str:
            return BIGINT()
        elif "float" in dtype_str or "double" in dtype_str:
            return NUMERIC(precision=18, scale=6)
        elif "bool" in dtype_str:
            return BOOLEAN()
        elif "datetime" in dtype_str or "timestamp" in dtype_str:
            return TIMESTAMP(timezone=True)
        else:
            return VARCHAR(255)
    
    def _create_table_from_parquet(
        self,
        table_name: str,
        parquet_path: str,
    ) -> bool:
        """
        Create PostgreSQL table from Parquet file schema.
        
        Args:
            table_name: Name of the table to create
            parquet_path: Path to Parquet file
        
        Returns:
            True if table created successfully
        """
        try:
            # Read Parquet file to get schema
            df = pd.read_parquet(parquet_path)
            
            if df.empty:
                self.logger.log(
                    "postgres_exporter",
                    "table_creation_skipped",
                    reason="Parquet file is empty",
                    table_name=table_name,
                )
                return False
            
            # Drop existing table if configured
            if DROP_EXISTING:
                with self.engine.connect() as conn:
                    conn.execute(text(f'DROP TABLE IF EXISTS "{POSTGRES_SCHEMA}"."{table_name}" CASCADE'))
                    conn.commit()
            
            # Create columns from DataFrame schema
            columns = []
            for col_name, dtype in df.dtypes.items():
                sql_type = self._get_sql_type(str(dtype))
                columns.append(Column(col_name, sql_type, nullable=True))
            
            # Add surrogate key if not present
            if "_surrogate_key" not in df.columns:
                columns.insert(0, Column("_surrogate_key", VARCHAR(36), nullable=False, primary_key=True))
            
            # Create table using SQLAlchemy
            table = Table(
                table_name,
                MetaData(schema=POSTGRES_SCHEMA),
                *columns,
            )
            
            table.create(self.engine, checkfirst=True)
            
            self.logger.log(
                "postgres_exporter",
                "table_created",
                table_name=table_name,
                column_count=len(columns),
            )
            print(f"[OK] Created table: {POSTGRES_SCHEMA}.{table_name}")
            
            return True
        
        except Exception as e:
            self.logger.log(
                "postgres_exporter",
                "table_creation_failed",
                table_name=table_name,
                error=str(e),
            )
            print(f"[ERROR] Failed to create table {table_name}: {e}")
            return False
    
    def export_parquet_to_table(
        self,
        table_name: str,
        parquet_path: str,
        truncate_first: bool = True,
    ) -> bool:
        """
        Export Parquet file data to PostgreSQL table.
        
        Args:
            table_name: Name of the target table
            parquet_path: Path to Parquet file
            truncate_first: Truncate table before inserting new data
        
        Returns:
            True if export successful
        """
        if not self.engine:
            return False
        
        try:
            # Read Parquet file
            df = pd.read_parquet(parquet_path)
            
            if df.empty:
                self.logger.log(
                    "postgres_exporter",
                    "export_skipped",
                    reason="Parquet file is empty",
                    table_name=table_name,
                )
                print(f"[WARN] Skipping {table_name} - no data in Parquet file")
                return False
            
            # Truncate table if configured
            if truncate_first:
                with self.engine.connect() as conn:
                    conn.execute(text(f'TRUNCATE TABLE "{POSTGRES_SCHEMA}"."{table_name}" CASCADE'))
                    conn.commit()
            
            # Insert data using SQLAlchemy's to_sql
            # This automatically creates table if it doesn't exist
            row_count = df.to_sql(
                table_name,
                self.engine,
                schema=POSTGRES_SCHEMA,
                if_exists="append",
                index=False,
                chunksize=1000,
                method="multi",
            )
            
            self.logger.log(
                "postgres_exporter",
                "export_success",
                table_name=table_name,
                row_count=len(df),
            )
            print(f"[OK] Exported {len(df)} rows to {POSTGRES_SCHEMA}.{table_name}")
            
            return True
        
        except Exception as e:
            self.logger.log(
                "postgres_exporter",
                "export_failed",
                table_name=table_name,
                error=str(e),
            )
            print(f"[ERROR] Export failed for {table_name}: {e}")
            return False
    
    def export_gold_layer(self, gold_output_paths: list[str]) -> Dict[str, bool]:
        """
        Export all Gold layer Parquet files to PostgreSQL.
        
        Args:
            gold_output_paths: List of Parquet file paths
        
        Returns:
            Dict mapping table_name -> success (True/False)
        """
        results = {}
        
        if not self.connect():
            return {Path(p).stem: False for p in gold_output_paths}
        
        for parquet_path in gold_output_paths:
            # Extract table name from filename (without .parquet)
            table_name = Path(parquet_path).stem
            
            # Create table first
            self._create_table_from_parquet(table_name, parquet_path)
            
            # Export data
            success = self.export_parquet_to_table(table_name, parquet_path)
            results[table_name] = success
        
        self._log_export_summary(results)
        return results
    
    def _log_export_summary(self, results: Dict[str, bool]) -> None:
        """Log summary of export results."""
        successful = sum(1 for v in results.values() if v)
        total = len(results)
        
        summary = f"PostgreSQL export: {successful}/{total} tables successful"
        self.logger.log("postgres_exporter", "export_summary", summary=summary)
        
        print("\n" + "="*70)
        print(f"PostgreSQL Export Summary: {successful}/{total} tables")
        print("="*70)
        for table_name, success in results.items():
            status = "[OK]" if success else "[ERROR]"
            print(f"{status} - {table_name}")
        print("="*70 + "\n")
    
    def close(self) -> None:
        """Close database connection."""
        if self.engine:
            self.engine.dispose()
            self.logger.log("postgres_exporter", "connection_closed")


# ─── Convenience Function ───────────────────────────────────────────────────

def export_gold_to_postgres(run_id: str, gold_output_paths: list[str]) -> Dict[str, bool]:
    """
    Export Gold layer to PostgreSQL.
    
    Args:
        run_id: Pipeline run ID
        gold_output_paths: List of Parquet file paths
    
    Returns:
        Dict mapping table_name -> success status
    """
    exporter = PostgreSQLExporter(run_id)
    try:
        return exporter.export_gold_layer(gold_output_paths)
    finally:
        exporter.close()
