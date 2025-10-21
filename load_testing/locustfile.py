from locust import HttpUser, task, between
import random
import uuid
from datetime import date

class AccountingSystemUser(HttpUser):
    wait_time = between(1, 3)
    host = "http://localhost:8000"  # Target the API Gateway

    def on_start(self):
        """Called when a Locust start before any task is scheduled."""
        # In a real test, you would log in to get a real token.
        self.access_token = "dummy-jwt-token-for-testing"
        self.tenant_id = "a1b2c3d4-e5f6-7890-1234-567890abcdef"
        self.headers = {
            "Authorization": f"Bearer {self.access_token}",
            "X-Tenant-ID": self.tenant_id,
            "Content-Type": "application/json"
        }

    @task(5)
    def create_transaction(self):
        """Simulates creating a new accounting transaction."""
        debit_account = f"a1b2c3d4-e5f6-1111-1111-{random.randint(100000000000, 999999999999)}"
        credit_account = f"a1b2c3d4-e5f6-2222-2222-{random.randint(100000000000, 999999999999)}"
        amount = round(random.uniform(10.0, 5000.0), 2)

        payload = {
            "transaction_date": date.today().isoformat(),
            "description": f"Locust test transaction {uuid.uuid4()}",
            "entries": [
                {"account_id": debit_account, "debit": amount, "credit": 0},
                {"account_id": credit_account, "debit": 0, "credit": amount}
            ]
        }
        self.client.post(
            "/api/v1/accounting/transactions", # Endpoint through the gateway
            json=payload,
            headers=self.headers,
            name="/api/v1/accounting/transactions"
        )

    @task(3)
    def get_accounts(self):
        """Simulates fetching the chart of accounts."""
        self.client.get(
            "/api/v1/accounting/accounts",
            headers=self.headers,
            name="/api/v1/accounting/accounts"
        )

    @task(1)
    def get_heavy_report(self):
        """Simulates a heavy report generation task."""
        start_date = "2025-01-01"
        end_date = date.today().isoformat()
        self.client.get(
            f"/api/v1/reporting/financial?start_date={start_date}&end_date={end_date}",
            headers=self.headers,
            name="/api/v1/reporting/financial"
        )

    @task(2)
    def calculate_vat(self):
        """Simulates a tax calculation."""
        payload = {
            "net_amount": round(random.uniform(100.0, 10000.0), 2),
            "is_exempt": random.choice([True, False])
        }
        self.client.post(
            "/api/v1/tax/vat/calculate",
            json=payload,
            headers=self.headers,
            name="/api/v1/tax/vat/calculate"
        )

# To run this test:
# 1. Install Locust: pip install locust
# 2. Run from the terminal in the project root: locust -f load_testing/locustfile.py
# 3. Open your browser to http://localhost:8089
