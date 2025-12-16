# Comparative Analysis: Raw SQL vs. Malloy vs. LookML

## Executive Summary
We stress-tested three query-authoring approaches against a realistic enterprise schema (9 tables, complex joins, derived metrics). The results highlight a clear trade-off between **flexibility** (Raw SQL) and **governance** (Malloy/LookML).

## Scenario Matrix

| Scenario | Raw SQL | Malloy | LookML | Best Fit |
| :--- | :--- | :--- | :--- | :--- |
| **1. Simple Aggregation** | ✅ **Success** | ✅ **Success** | ✅ **Success** | **Raw SQL** (Fastest, no overhead) |
| **2. Governed Metric** | ⚠️ **Risky** | ✅ **Success** | ✅ **Success** | **Malloy/LookML** (Guarantees logic) |
| **3. Deep Join** | ❌ **Failure** (Often misses join keys) | ✅ **Success** (Pre-defined joins) | ✅ **Success** (Pre-defined joins) | **LookML** (Strongest join management) |
| **4. Derived Dimension** | ❌ **Failure** (Hallucinates logic) | ✅ **Success** (Encapsulated logic) | ✅ **Success** (Encapsulated logic) | **Malloy** (Flexible definitions) |
| **5. Safety Check** | 🛑 **Blocked** | 🛑 **Blocked** | 🛑 **Blocked** | **Judge Agent** (Essential for all) |

## Detailed Findings

### 1. Raw SQL
-   **Strengths**: Universal, no setup required, great for simple "SELECT * FROM" or basic aggregations.
-   **Weaknesses**:
    -   **Hallucination Risk**: Frequently guesses column names (e.g., `customer_id` vs `cust_id`).
    -   **Logic Drift**: "Total Revenue" might be calculated differently in every query (ignoring refunds, currency).
    -   **Join Complexity**: Struggles with multi-hop joins (Txn -> Acct -> Cust -> Branch).

### 2. Malloy (Semantic Layer)
-   **Strengths**:
    -   **Governance**: Metrics like `total_revenue` are defined once and reused.
    -   **Join Safety**: Joins are pre-defined in the source, preventing fan-out errors.
    -   **Composability**: Easy to refine queries (e.g., `nest: by_month`).
-   **Weaknesses**: Requires a compilation step (simulated here, but adds latency in prod).

### 3. LookML (Enterprise Standard)
-   **Strengths**:
    -   **Production Parity**: Matches what business users see in dashboards.
    -   **Robust Modeling**: Handles complex derived dimensions (like `segment`) elegantly.
-   **Weaknesses**: Verbose to write; requires a Looker instance/API.

## Staff Engineer Assessment

**Recommendation: Hybrid Approach**

1.  **Use LookML/Malloy for Business Metrics**:
    -   For anything involving **Revenue**, **Churn**, or **Segmentation**, do NOT rely on Raw SQL. The risk of logic drift is too high.
    -   Use the Semantic Layer to "compile" the correct SQL logic (currency conversion, refund exclusion) before execution.

2.  **Use Raw SQL for Ad-Hoc Exploration**:
    -   For simple counts, checking table schemas, or one-off debugging, Raw SQL is faster and sufficient.
    -   *Crucial*: Always wrap Raw SQL generation in a **Judge Agent** to prevent destructive operations.

3.  **The "Judge" is Mandatory**:
    -   Regardless of the method, an AI Judge is essential to catch hallucinations (invalid columns) and unsafe operations (DELETE/DROP) before they hit the database.
