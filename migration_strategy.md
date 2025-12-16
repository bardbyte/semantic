# Strategy: Migrating Legacy SQL to Semantic Layers

## The Challenge
You have a repository of "Raw SQL" queries (legacy reports, ad-hoc scripts) and want to move to a governed Semantic Layer (LookML or Malloy).
-   **Direct Use?** You *can* run them (as we showed in "Mode 1"), but you inherit all the risks: drift, lack of governance, and maintenance nightmares.
-   **Manual Rewrite?** Too slow and expensive.

## The Solution: AI-Driven "Reverse Engineering"

We can build a **Migration Agent** to automate this conversion. This is not just "translation"; it is "refactoring."

### Phase 1: Pattern Recognition (The "Archaeologist" Agent)
Instead of converting one query at a time, the agent scans your query logs (e.g., BigQuery `INFORMATION_SCHEMA`).
1.  **Cluster**: It groups queries that touch the same tables.
2.  **Identify Patterns**: It spots repeated logic.
    -   *Example*: "90% of queries on `fct_transactions` filter by `status = 'ACTIVE'`."
    -   *Insight*: "This should be a permanent filter in the Semantic Model."
3.  **Extract Metrics**: It finds repeated aggregations.
    -   *Example*: "Sum of `amount` where `currency='EUR'` * 1.1" appears 50 times.
    -   *Insight*: "This is the definition of `Total Revenue`. Let's define it once."

### Phase 2: Code Generation (The "Architect" Agent)
The agent takes these insights and writes the LookML/Malloy files.
-   **Input**: Raw SQL Pattern: `SELECT sum(amt) FROM txns WHERE status='active'`
-   **Output (LookML)**:
    ```lookml
    measure: total_revenue {
      type: sum
      sql: ${amount} ;;
      filters: [status: "active"]
    }
    ```

### Phase 3: Verification (The "Judge" Agent)
We use the same "Judge" concept from our PoC, but in reverse.
1.  Run the original Legacy SQL.
2.  Run the new Semantic Query (compiled to SQL).
3.  **Compare Results**: If they match, the migration is verified.

## Workflow: "The Strangler Fig" Pattern
You don't need to migrate everything at once.
1.  **Wrap**: Route all legacy SQL through the **Judge Agent** (as we did in the PoC).
2.  **Identify**: The Judge flags "High Frequency / High Risk" queries.
3.  **Migrate**: The Migration Agent converts those specific queries to LookML/Malloy.
4.  **Replace**: Users start querying the Semantic Layer; legacy SQL is deprecated.

## Feasibility
This is highly feasible.
-   **Looker** already has a "Create View from Table" feature, but it's basic.
-   **Malloy** is designed to be inferred from schema.
-   **GenAI** bridges the gap by understanding the *intent* of the `WHERE` clauses and naming the metrics meaningfully.
