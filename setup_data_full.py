import pandas as pd
from google.cloud import bigquery
from faker import Faker
import random
import datetime

# CONFIG
PROJECT_ID = "semantic-poc-2025"
DATASET_ID = "lumi_enterprise_raw"

client = bigquery.Client(project=PROJECT_ID)
fake = Faker()

def create_dataset():
    ds_ref = bigquery.Dataset(f"{PROJECT_ID}.{DATASET_ID}")
    ds_ref.location = "US"
    try:
        client.create_dataset(ds_ref, exists_ok=True)
        print(f"✅ Dataset {DATASET_ID} ready.")
    except Exception as e:
        print(f"Dataset error: {e}")

def generate_data():
    print("🏭 Generating 9-Table Enterprise Data...")
    
    # 1. Geography (Dim)
    branches = [{"branch_id": f"B_{i}", "state": fake.state_abbr(), "manager": fake.name()} for i in range(10)]
    
    # 2. Products (Dim)
    products = [
        {"prod_code": "P_PLAT", "name": "Platinum Card", "fee": 550},
        {"prod_code": "P_GOLD", "name": "Gold Card", "fee": 250},
        {"prod_code": "P_BLUE", "name": "Blue Cash", "fee": 0}
    ]
    
    # 3. Customers (Dim)
    customers = []
    for i in range(100):
        customers.append({
            "cust_id": f"C_{i}", 
            "branch_id": random.choice(branches)['branch_id'],
            "name": fake.name(),
            "risk_score": random.randint(300, 850)
        })

    # 4. Accounts (Dim) - The Bridge
    accounts = []
    for c in customers:
        for _ in range(random.randint(1, 3)):
            accounts.append({
                "acct_id": f"A_{fake.uuid4()[:8]}",
                "cust_id": c['cust_id'],
                "prod_code": random.choice(products)['prod_code'],
                "status": random.choice(['ACTIVE', 'CLOSED', 'CHURNED'])
            })

    # 5. Merchants (Dim)
    merchants = [{"merch_id": f"M_{i}", "name": fake.company(), "category": random.choice(['Travel', 'Retail', 'Dining'])} for i in range(20)]

    # 6. Campaigns (Dim) - Marketing Data
    campaigns = [{"camp_id": f"CMP_{i}", "name": f"Promo {2024+i}", "channel": "Email"} for i in range(5)]

    # 7. Transactions (Fact) - The Volume
    transactions = []
    for a in accounts:
        for _ in range(random.randint(5, 20)):
            amt = round(random.uniform(10, 2000), 2)
            if random.random() < 0.1: amt = amt * -1 # Refund trap
            curr = 'EUR' if random.random() < 0.15 else 'USD' # Currency trap
            
            transactions.append({
                "txn_id": fake.uuid4(),
                "acct_id": a['acct_id'],
                "merch_id": random.choice(merchants)['merch_id'],
                "amount": amt,
                "currency": curr,
                "txn_date": str(fake.date_between(start_date='-1y', end_date='today'))
            })

    # 8. Disputes (Fact) - Risk Data
    disputes = []
    for t in transactions:
        if random.random() < 0.05: # 5% dispute rate
            disputes.append({
                "dispute_id": fake.uuid4(),
                "txn_id": t['txn_id'],
                "reason": random.choice(['Fraud', 'Duplicate', 'Not Recognized']),
                "status": random.choice(['OPEN', 'RESOLVED'])
            })

    # 9. Campaign Responses (Fact) - Marketing Join
    responses = []
    for c in customers:
        if random.random() < 0.3:
            responses.append({
                "resp_id": fake.uuid4(),
                "cust_id": c['cust_id'],
                "camp_id": random.choice(campaigns)['camp_id'],
                "responded_at": str(fake.date_this_year())
            })

    return {
        "dim_branches": pd.DataFrame(branches),
        "dim_products": pd.DataFrame(products),
        "dim_customers": pd.DataFrame(customers),
        "dim_accounts": pd.DataFrame(accounts),
        "dim_merchants": pd.DataFrame(merchants),
        "dim_campaigns": pd.DataFrame(campaigns),
        "fct_transactions": pd.DataFrame(transactions),
        "fct_disputes": pd.DataFrame(disputes),
        "fct_responses": pd.DataFrame(responses)
    }

def upload(dfs):
    job_config = bigquery.LoadJobConfig(write_disposition="WRITE_TRUNCATE")
    for name, df in dfs.items():
        print(f"  Uploading {name}...")
        client.load_table_from_dataframe(df, f"{DATASET_ID}.{name}", job_config).result()
    print("✅ All 9 Tables Uploaded.")

if __name__ == "__main__":
    create_dataset()
    data = generate_data()
    upload(data)
