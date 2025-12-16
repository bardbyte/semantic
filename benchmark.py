import vertexai
from vertexai.generative_models import GenerativeModel
from google.cloud import bigquery
import pandas as pd
import time
import json

# --- CONFIGURATION ---
PROJECT_ID = "semantic-poc-2025"
LOCATION = "us-central1"
DATASET_ID = "lumi_enterprise_raw" # Updated to match setup_data_full.py

# Initialize Clients
bq_client = bigquery.Client(project=PROJECT_ID)
vertexai.init(project=PROJECT_ID, location=LOCATION)

# --- THE "GOLD STANDARD" KERNEL ---
# This dictionary represents what the Semantic Layer (Malloy) 'Compiles' to.
# It is the GUARANTEED TRUTH.
SEMANTIC_DEFINITIONS = {
    "total_revenue": """
        -- COMPILED FROM: finance.malloy
        -- LOGIC: Exclude Refunds, Convert EUR->USD, Only Active Accounts
        SELECT 
            c.segment,
            SUM(
                CASE 
                    WHEN t.currency = 'EUR' THEN t.amount * 1.1 
                    ELSE t.amount 
                END
            ) as metric_value
        FROM `{project}.{dataset}.fct_transactions` t
        JOIN `{project}.{dataset}.dim_accounts` a ON t.acct_id = a.acct_id
        JOIN `{project}.{dataset}.dim_customers` c ON a.cust_id = c.cust_id
        WHERE t.amount > 0 AND a.status = 'ACTIVE'
        GROUP BY 1
        ORDER BY 1
    """,
    "active_customer_count": """
        -- COMPILED FROM: finance.malloy
        -- LOGIC: Distinct Customers with at least one transaction in Active status
        SELECT 
            c.segment,
            COUNT(DISTINCT c.cust_id) as metric_value
        FROM `{project}.{dataset}.dim_customers` c
        JOIN `{project}.{dataset}.dim_accounts` a ON c.cust_id = a.cust_id
        JOIN `{project}.{dataset}.fct_transactions` t ON a.acct_id = t.acct_id
        WHERE a.status = 'ACTIVE'
        GROUP BY 1
        ORDER BY 1
    """
}

class BenchmarkEngine:
    def __init__(self):
        self.model = GenerativeModel("gemini-2.5-flash")

    def execute_bq(self, sql, query_type):
        """Executes SQL and captures cost/performance metrics."""
        try:
            start_time = time.time()
            job_config = bigquery.QueryJobConfig(use_query_cache=False) # Force real execution
            query_job = bq_client.query(sql, job_config=job_config)
            results = query_job.result()
            duration = time.time() - start_time
            
            # Extract single aggregated value for comparison (simplified for demo)
            total_val = 0
            rows = []
            for row in results:
                rows.append(dict(row))
                # Try to find the numeric column
                for val in row.values():
                    if isinstance(val, (int, float)):
                        total_val += val
                        break
            
            return {
                "status": "SUCCESS",
                "sql": sql,
                "total_value": round(total_val, 2),
                "bytes_scanned": query_job.total_bytes_processed,
                "duration_ms": round(duration * 1000, 2),
                "rows": rows
            }
        except Exception as e:
            return {
                "status": "FAILED",
                "error": str(e),
                "sql": sql
            }

    def execute_generated_sql(self, sql, query_type):
        """Executes externally generated SQL and returns metrics."""
        return self.execute_bq(sql, query_type)

    def print_comparison(self, raw, sem):
        if raw['status'] == 'FAILED':
            print("❌ RAW SQL FAILED TO EXECUTE.")
            print(f"   Error: {raw['error']}")
            return

        # Calculate Variance
        val_raw = raw.get('total_value', 0)
        val_sem = sem.get('total_value', 0)
        
        if val_sem == 0: variance = 0
        else: variance = ((val_raw - val_sem) / val_sem) * 100
        
        print("\n📊 BENCHMARK RESULTS")
        print(f"{'Metric':<20} | {'Raw SQL':<20} | {'Semantic Layer':<25} | {'Delta':<10}")
        print("-" * 85)
        print(f"{'Total Value':<20} | {val_raw:<20} | {val_sem:<25} | {variance:.2f}%")
        print(f"{'Bytes Scanned':<20} | {raw.get('bytes_scanned',0):<20} | {sem.get('bytes_scanned',0):<25} | -")
        print(f"{'Execution Time':<20} | {raw.get('duration_ms',0)}ms{'':<16} | {sem.get('duration_ms',0)}ms{'':<21} | -")
