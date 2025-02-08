import sys
import json
import boto3
from pyspark.sql import SparkSession
from pyspark.sql.functions import (
    col, when, current_timestamp, expr, round as spark_round
)
from pyspark.sql.types import DecimalType
from awsglue.context import GlueContext
from awsglue.dynamicframe import DynamicFrame
from awsglue.utils import getResolvedOptions

# Initialize Spark and Glue Context
spark = SparkSession.builder \
    .appName("Glue-Hudi-Crypto-ETL") \
    .config("spark.serializer", "org.apache.spark.serializer.KryoSerializer") \
    .config("spark.sql.hive.convertMetastoreParquet", "false") \
    .getOrCreate()

glueContext = GlueContext(spark)
spark.sql("set spark.sql.legacy.timeParserPolicy=LEGACY")


SOURCE_DATABASE = "crypto" 
SOURCE_TABLE = "crypto_raw"        
HUDI_DATABASE = "crypto" 
HUDI_TABLE = "processed_crypto_txn"           
HUDI_PATH = "s3://crypto-post-processing/crypto_processed/"              

# Read incremental data from Glue Catalog
firehose_df = glueContext.create_dynamic_frame.from_catalog(
    database=SOURCE_DATABASE, table_name=SOURCE_TABLE
).toDF()

# Apply Data Type Conversions
firehose_df = firehose_df \
    .withColumn("quantity", col("quantity").cast(DecimalType(10, 6))) \
    .withColumn("price", col("price").cast(DecimalType(10, 2))) \
    .withColumn("trade_fee", col("trade_fee").cast(DecimalType(10, 4))) \
    .withColumn("ingestion_time", current_timestamp())


# Flag High-Risk Transactions (Large Trades)
firehose_df = firehose_df.withColumn(
    "risk_flag",
    when(col("quantity") * col("price") > 500000, "HIGH_RISK")
    .when(col("quantity") * col("price") > 100000, "MEDIUM_RISK")
    .otherwise("LOW_RISK")
)

# Normalize Prices Across Exchanges (Price Variance Adjustment)
exchange_price_multiplier = {
    "Binance": 1.00,
    "Coinbase": 1.02,
    "Kraken": 0.98,
    "OKX": 1.01,  
    "FTX": 0.99,
    "Bitfinex": 1.03
}

exchange_case_expr = "CASE " + " ".join([
    f"WHEN exchange = '{exch}' THEN price * {factor}" for exch, factor in exchange_price_multiplier.items()
]) + " ELSE price END"

firehose_df = firehose_df.withColumn("normalized_price", expr(exchange_case_expr).cast(DecimalType(10, 2)))

# Assign Fee Tier Based on Transaction Amount
firehose_df = firehose_df.withColumn(
    "adjusted_trade_fee",
    when(col("quantity") * col("price") >= 100000, col("trade_fee") * 0.9) 
    .when(col("quantity") * col("price") >= 50000, col("trade_fee") * 0.95)
    .otherwise(col("trade_fee"))
)

# Categorize Users Based on Trading Volume
firehose_df = firehose_df.withColumn(
    "user_category",
    when(col("quantity") > 2, "VIP Trader")
    .when(col("quantity") > 1, "Active Trader")
    .otherwise("Casual Trader")
)

# Convert Timestamp to Time Bucket (For Market Analysis)
firehose_df = firehose_df.withColumn(
    "hour_bucket",
    expr("date_format(timestamp, 'yyyy-MM-dd HH:00:00')")
)

# Filter Out Non-Matching Trades
firehose_df = firehose_df.filter(
    (col("trade_status") != "FAILED") & 
    (col("quantity") > 0) &
    (col("price") > 0)
)

# === WRITE DATA TO HUDI TABLE === #

hudi_options = {
    "hoodie.table.name": HUDI_TABLE,
    "hoodie.datasource.write.storage.type": "COPY_ON_WRITE",
    "hoodie.datasource.write.recordkey.field": "transaction_id",
    "hoodie.datasource.write.partitionpath.field": "exchange",
    "hoodie.datasource.write.precombine.field": "timestamp",
    "hoodie.datasource.write.operation": "upsert",
    "hoodie.datasource.hive_sync.enable": "true",
    "hoodie.datasource.hive_sync.database": HUDI_DATABASE,
    "hoodie.datasource.hive_sync.table": HUDI_TABLE,
    "hoodie.datasource.hive_sync.partition_fields": "exchange",
    "hoodie.datasource.hive_sync.mode": "hms",
    "path": HUDI_PATH
}

# Create Hudi Table if it does not exist
spark.sql(f"CREATE DATABASE IF NOT EXISTS {HUDI_DATABASE}")

# Perform Hudi Merge Operation
firehose_df.write.format("hudi").options(**hudi_options).mode("append").save()

print("Hudi Upsert Completed Successfully !!")