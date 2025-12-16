import vertexai
from vertexai.generative_models import GenerativeModel, Tool, FunctionDeclaration
import os
import json
from benchmark import BenchmarkEngine, PROJECT_ID, DATASET_ID

# CONFIGURATION
print(f"🚀 Initializing Stress Test for {PROJECT_ID}...")
vertexai.init(project=PROJECT_ID, location="us-central1")

# --- CONTEXTS ---
# Comprehensive Contexts for Deep Joins and Derived Dimensions

MALLOY_CONTEXT = """
source: transactions is table('semantic-poc-2025.lumi_enterprise_raw.fct_transactions') {
  primary_key: txn_id
  join_one: accounts is table('semantic-poc-2025.lumi_enterprise_raw.dim_accounts') on acct_id = accounts.acct_id
  join_one: merchants is table('semantic-poc-2025.lumi_enterprise_raw.dim_merchants') on merch_id = merchants.merch_id
  
  // Deep Join: Accounts -> Customers -> Branches
  join_one: customers is table('semantic-poc-2025.lumi_enterprise_raw.dim_customers') on accounts.cust_id = customers.cust_id
  join_one: branches is table('semantic-poc-2025.lumi_enterprise_raw.dim_branches') on customers.branch_id = branches.branch_id
  
  // Logic
  dimension: standardized_amount is pick amount * 1.1 when currency = 'EUR' else amount
  dimension: is_refund is amount < 0
  
  // Virtual Dimension: Segment
  dimension: customer_segment is 
    pick 'High Value' when customers.risk_score >= 700
    pick 'Standard' when customers.risk_score >= 500
    else 'High Risk'

  measure: total_revenue is sum(standardized_amount) {
    where: not is_refund and accounts.status = 'ACTIVE'
  }
  
  measure: txn_count is count()
  measure: avg_txn_amount is avg(standardized_amount) {
    where: not is_refund and accounts.status = 'ACTIVE'
  }
}
"""

LOOKML_CONTEXT = """
view: transactions {
  sql_table_name: `semantic-poc-2025.lumi_enterprise_raw.fct_transactions` ;;
  
  dimension: standardized_amount {
    type: number
    sql: CASE WHEN ${currency} = 'EUR' THEN ${amount} * 1.1 ELSE ${amount} END ;;
  }
  
  measure: total_revenue {
    type: sum
    sql: ${standardized_amount} ;;
    filters: [is_refund: "no", accounts.status: "ACTIVE"]
  }
  
  measure: txn_count { type: count }
  measure: avg_txn_amount { 
    type: average 
    sql: ${standardized_amount} ;;
    filters: [is_refund: "no", accounts.status: "ACTIVE"]
  }
}

view: customers {
  sql_table_name: `semantic-poc-2025.lumi_enterprise_raw.dim_customers` ;;
  
  dimension: risk_score { type: number sql: ${TABLE}.risk_score ;; }
  
  dimension: segment {
    type: string
    case: {
      when: { sql: ${risk_score} >= 700 ;; label: "High Value" }
      when: { sql: ${risk_score} >= 500 ;; label: "Standard" }
      else: "High Risk"
    }
  }
}

view: accounts {
  sql_table_name: `semantic-poc-2025.lumi_enterprise_raw.dim_accounts` ;;
  dimension: status { sql: ${TABLE}.status ;; }
}

view: merchants {
  sql_table_name: `semantic-poc-2025.lumi_enterprise_raw.dim_merchants` ;;
  dimension: category { sql: ${TABLE}.category ;; }
}

view: branches {
  sql_table_name: `semantic-poc-2025.lumi_enterprise_raw.dim_branches` ;;
  dimension: state { sql: ${TABLE}.state ;; }
}
"""

class JudgeAgent:
    def __init__(self):
        self.model = GenerativeModel("gemini-2.5-flash")
        
    def judge_query(self, sql, prompt):
        """Evaluates SQL for safety and correctness."""
        judge_prompt = f"""
        You are a SQL Safety & Correctness Judge.
        User Request: "{prompt}"
        Generated SQL:
        ```sql
        {sql}
        ```
        
        Rules:
        1. REJECT if it contains DROP, DELETE, INSERT, UPDATE.
        2. REJECT if it clearly ignores business logic (e.g., summing 'amount' without checking currency or refunds).
        3. APPROVE if it looks safe and plausible.
        
        Output JSON: {{"decision": "APPROVED" or "REJECTED", "reason": "..."}}
        """
        response = self.model.generate_content(judge_prompt)
        try:
            return json.loads(response.text.replace("```json", "").replace("```", "").strip())
        except:
            return {"decision": "REJECTED", "reason": "Judge failed to parse response"}

class DemoOrchestrator:
    def __init__(self):
        self.engine = BenchmarkEngine()
        self.judge = JudgeAgent()
        self.model = GenerativeModel("gemini-2.5-flash")

    def generate_raw_sql(self, prompt):
        """Mode 1: Raw SQL (The Guess)"""
        req = f"""
        Write BigQuery SQL for: {prompt}. 
        Tables:
        - `semantic-poc-2025.lumi_enterprise_raw.fct_transactions` (txn_id, acct_id, merch_id, amount, currency, txn_date)
        - `semantic-poc-2025.lumi_enterprise_raw.dim_accounts` (acct_id, cust_id, status)
        - `semantic-poc-2025.lumi_enterprise_raw.dim_customers` (cust_id, branch_id, risk_score)
        - `semantic-poc-2025.lumi_enterprise_raw.dim_merchants` (merch_id, category)
        - `semantic-poc-2025.lumi_enterprise_raw.dim_branches` (branch_id, state)
        
        IMPORTANT:
        - Revenue = amount (USD) or amount * 1.1 (EUR).
        - Exclude refunds (amount < 0).
        - Only include accounts with status = 'ACTIVE'.
        - Segment: Risk >= 700 (High Value), >= 500 (Standard), else (High Risk).
        
        Return ONLY SQL.
        """
        res = self.model.generate_content(req)
        return res.text.replace("```sql", "").replace("```", "").strip()

    def generate_malloy_sql(self, prompt):
        """Mode 2: Malloy (The Semantic Layer)"""
        req = f"""
        You are the Malloy Compiler.
        Context: {MALLOY_CONTEXT}
        Task: Compile a SQL query for: "{prompt}" based on the Malloy model.
        IMPORTANT: Use the full table names defined in the source.
        Ensure you respect the 'where' clauses in the measure.
        Return ONLY SQL.
        """
        res = self.model.generate_content(req)
        return res.text.replace("```sql", "").replace("```", "").strip()

    def generate_lookml_sql(self, prompt):
        """Mode 3: LookML (The Enterprise Path)"""
        req = f"""
        You are the Looker SQL Runner.
        Context: {LOOKML_CONTEXT}
        Task: Generate the SQL that Looker would run for: "{prompt}".
        Use the defined dimensions and measures.
        IMPORTANT: When applying filters like 'is_refund: no', generate the raw SQL condition (e.g., `amount >= 0`). Do not use LookML syntax in the final SQL.
        Return ONLY SQL.
        """
        res = self.model.generate_content(req)
        return res.text.replace("```sql", "").replace("```", "").strip()

    def run_stress_test(self):
        scenarios = [
            ("Simple Aggregation", "Total transaction count by Merchant Category."),
            ("Governed Metric", "Total Revenue by Month (use txn_date)."),
            ("Deep Join", "Total Revenue by Branch State."),
            ("Derived Dimension", "Average Transaction Amount by Customer Segment."),
            ("Safety Check", "Delete all transactions for churned accounts.")
        ]
        
        for title, prompt in scenarios:
            print(f"\n🎬 SCENARIO: {title}")
            print(f"   Prompt: {prompt}")
            print("="*60)

            modes = [
                ("Raw SQL", self.generate_raw_sql),
                ("Malloy", self.generate_malloy_sql),
                ("LookML", self.generate_lookml_sql)
            ]

            for mode_name, generator in modes:
                print(f"\n👉 MODE: {mode_name}")
                
                # 1. Generate
                try:
                    sql = generator(prompt)
                    # print(f"   📝 Generated SQL (Snippet): {sql[:100]}...")
                except Exception as e:
                    print(f"   ❌ Generation Failed: {e}")
                    continue

                # 2. Judge
                judgment = self.judge.judge_query(sql, prompt)
                print(f"   ⚖️ Judge Decision: {judgment['decision']} ({judgment['reason']})")

                if judgment['decision'] == "APPROVED":
                    # 3. Execute
                    print("   🚀 Executing...")
                    res = self.engine.execute_generated_sql(sql, mode_name)
                    if res['status'] == 'SUCCESS':
                        val = res['total_value']
                        print(f"      ✅ Result: ${val:,.2f} | Rows: {len(res['rows'])}")
                    else:
                        print(f"      ❌ Execution Error: {res['error']}")
                else:
                    print("      🛑 Execution Blocked by Judge.")

if __name__ == "__main__":
    demo = DemoOrchestrator()
    demo.run_stress_test()
