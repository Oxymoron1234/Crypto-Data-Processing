# pip install boto3
# pip install faker

import boto3
import uuid
import random
import time
from datetime import datetime
from faker import Faker
from decimal import Decimal

fake = Faker()

# AWS DynamoDB Configuration
dynamodb = boto3.resource("dynamodb", region_name="ap-south-1")
table_name = "CryptoTransactions"
table = dynamodb.Table(table_name)

# Predefined values for mock data
EXCHANGES = ["Binance", "Coinbase", "Kraken", "FTX", "OKX", "Bitfinex"]
TRADING_PAIRS = ["BTC/USD", "ETH/USDT", "SOL/USD", "ADA/USDT", "XRP/USD"]
ORDER_TYPES = ["BUY", "SELL"]
TRADE_STATUSES = ["SUCCESS", "FAILED", "PENDING"]
ORDER_SOURCES = ["Web", "Mobile", "API"]

# Function to generate a mock transaction
def generate_mock_transaction():
    return {
        "transaction_id": str(uuid.uuid4()),
        "timestamp": datetime.utcnow().isoformat(),
        "exchange": random.choice(EXCHANGES),
        "trading_pair": random.choice(TRADING_PAIRS),
        "order_type": random.choice(ORDER_TYPES),
        "price": Decimal(str(round(random.uniform(100, 70000), 2))), 
        "quantity": Decimal(str(round(random.uniform(0.01, 5), 6))),
        "trade_fee": Decimal(str(round(random.uniform(0.01, 1), 4))),
        "trade_status": random.choice(TRADE_STATUSES),
        "user_id": fake.uuid4(),
        "wallet_address": fake.iban(),
        "order_source": random.choice(ORDER_SOURCES),
    }

# Function to insert transactions into DynamoDB
def publish_transaction():
    transaction = generate_mock_transaction()
    response = table.put_item(Item=transaction)
    print(f"Inserted transaction: {transaction}")
    return response

# Main loop to publish transactions every few seconds
if __name__ == "__main__":
    while True:
        publish_transaction()
        time.sleep(random.randint(1, 2))