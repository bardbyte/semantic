view: transactions {
  sql_table_name: `semantic-poc-2025.lumi_enterprise_raw.fct_transactions` ;;

  dimension: txn_id {
    primary_key: yes
    type: string
    sql: ${TABLE}.txn_id ;;
  }

  dimension: amount {
    type: number
    sql: ${TABLE}.amount ;;
  }

  dimension: currency {
    type: string
    sql: ${TABLE}.currency ;;
  }

  # LOGIC: Currency Normalization
  dimension: standardized_amount {
    type: number
    sql: CASE WHEN ${currency} = 'EUR' THEN ${amount} * 1.1 ELSE ${amount} END ;;
  }

  dimension: is_refund {
    type: yesno
    sql: ${amount} < 0 ;;
  }

  # METRIC: Total Revenue
  measure: total_revenue {
    type: sum
    sql: ${standardized_amount} ;;
    filters: [is_refund: "no", accounts.status: "ACTIVE"]
  }
}

view: customers {
  sql_table_name: `semantic-poc-2025.lumi_enterprise_raw.dim_customers` ;;

  dimension: cust_id {
    primary_key: yes
    type: string
    sql: ${TABLE}.cust_id ;;
  }

  dimension: risk_score {
    type: number
    sql: ${TABLE}.risk_score ;;
  }

  # LOGIC: Virtual Dimension
  dimension: segment {
    type: string
    case: {
      when: {
        sql: ${risk_score} >= 700 ;;
        label: "High Value"
      }
      when: {
        sql: ${risk_score} >= 500 ;;
        label: "Standard"
      }
      else: "High Risk"
    }
  }
}

view: accounts {
  sql_table_name: `semantic-poc-2025.lumi_enterprise_raw.dim_accounts` ;;

  dimension: acct_id {
    primary_key: yes
    type: string
    sql: ${TABLE}.acct_id ;;
  }

  dimension: status {
    type: string
    sql: ${TABLE}.status ;;
  }
}

explore: transactions {
  join: accounts {
    type: left_outer
    sql_on: ${transactions.acct_id} = ${accounts.acct_id} ;;
    relationship: many_to_one
  }
  join: customers {
    type: left_outer
    sql_on: ${accounts.cust_id} = ${customers.cust_id} ;;
    relationship: many_to_one
  }
}
