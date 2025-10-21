from sqlalchemy import create_engine
import pandas as pd
from uuid import uuid4
import asyncio

# This is a placeholder class based on the migration plan.
# Connection details and actual table names/schemas will need to be adjusted.

class DataSynchronizer:
    def __init__(self):
        # TODO: Replace with actual legacy database connection string
        self.legacy_engine = create_engine('postgresql://user:password@legacy_db_host/legacy_db')
        # TODO: Replace with actual new database connection details
        self.new_db_params = {
            'user': 'user',
            'password': 'password',
            'host': 'postgres-new',
            'database': 'accounting_new'
        }
        self.new_pool = None

    async def get_new_db_connection(self):
        # Dynamically import asyncpg to avoid dependency if not used
        import asyncpg
        if not self.new_pool:
            self.new_pool = await asyncpg.create_pool(**self.new_db_params)
        return self.new_pool

    async def sync_accounts(self):
        """Синхронизация справочника счетов"""
        print("Starting account synchronization...")
        try:
            # In a real scenario, you'd connect to the legacy DB.
            # For this example, we'll create a dummy DataFrame.
            # df = pd.read_sql("SELECT * FROM chart_of_accounts", self.legacy_engine)
            
            dummy_data = {
                'code': ['1110', '1210', '3110', '4110'],
                'name': ['Cash', 'Accounts Receivable', 'Accounts Payable', 'Sales Revenue'],
                'account_type': ['ASSET', 'ASSET', 'LIABILITY', 'REVENUE']
            }
            df = pd.DataFrame(dummy_data)
            print(f"Found {len(df)} accounts in legacy system (dummy data).")

            # Transform data
            df['id'] = [uuid4() for _ in range(len(df))]
            df['created_at'] = pd.Timestamp.now()
            
            print("Transforming data for the new system...")

            # Load to new system
            pool = await self.get_new_db_connection()
            async with pool.acquire() as conn:
                # NOTE: The target table 'accounts' and its schema must exist in the new database.
                # This script assumes a table like:
                # CREATE TABLE accounts (id UUID, code VARCHAR, name VARCHAR, type VARCHAR, created_at TIMESTAMP);
                await conn.executemany(
                    "INSERT INTO accounts (id, code, name, type, created_at) VALUES ($1, $2, $3, $4, $5)",
                    [(row['id'], row['code'], row['name'], row['account_type'], row['created_at']) for index, row in df.iterrows()]
                )
            print("Successfully loaded data into the new system.")
        except Exception as e:
            print(f"An error occurred during synchronization: {e}")

async def main():
    synchronizer = DataSynchronizer()
    await synchronizer.sync_accounts()

if __name__ == "__main__":
    # Note: This script requires pandas and asyncpg to be installed.
    # You might need to run: pip install pandas asyncpg sqlalchemy
    # Also, ensure the postgres-new service is running and accessible.
    asyncio.run(main())
