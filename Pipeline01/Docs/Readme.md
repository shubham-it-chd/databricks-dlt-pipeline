## Step 1: Set Up JDBC Connection Details
```sql
jdbc:sqlserver://<hostname>:<port>;databaseName=SampleDB
```

### Credentials
```sh
databricks secrets create-scope --scope sqlserver
databricks secrets put --scope sqlserver --key username
databricks secrets put --scope sqlserver --key password
```

### Connection Properties: 
Define the JDBC connection properties in your DLT code, including the driver and credentials.

## Step 2: Create the DLT Notebook
Create a new notebook in Databricks (set to Python) and add the following DLT pipeline code. This example:

Reads the dbo.Sales table into a Bronze layer.
Applies data quality checks in the Silver layer (e.g., non-null ID, positive Amount).
Aggregates data in the Gold layer (e.g., total sales by date).
```python
import dlt
from pyspark.sql.functions import *

# JDBC connection configuration
jdbc_url = "jdbc:sqlserver://<hostname>:<port>;databaseName=SampleDB"
connection_properties = {
    "user": dbutils.secrets.get(scope="sqlserver", key="username"),
    "password": dbutils.secrets.get(scope="sqlserver", key="password"),
    "driver": "com.microsoft.sqlserver.jdbc.SQLServerDriver"
}

# Bronze Layer: Ingest raw data from dbo.Sales
@dlt.table(
    comment="Raw sales data from SQL Server",
    table_properties={"dataLayer": "bronze"}
)
def sales_bronze():
    return (
        spark.read
        .format("jdbc")
        .option("url", jdbc_url)
        .option("dbtable", "dbo.Sales")  # Specify the table
        .option("fetchsize", "1000")     # Optimize fetch size for performance
        .options(**connection_properties)
        .load()
    )

# Silver Layer: Clean data with quality checks
@dlt.table(
    comment="Cleaned sales data",
    table_properties={"dataLayer": "silver"}
)
@dlt.expect_or_drop("non_null_id", "ID IS NOT NULL")
@dlt.expect_or_drop("valid_amount", "Amount > 0")
def sales_silver():
    return (
        dlt.read("sales_bronze")
        .select(
            col("ID"),
            col("TransactionDate"),
            col("Amount"),
            col("CustomerID"),
            col("ProductID"),
            col("Quantity"),
            col("Notes")
        )
        .filter(col("Quantity") > 0)  # Additional cleaning
    )

# Gold Layer: Aggregate total sales by date
@dlt.table(
    comment="Aggregated sales by transaction date",
    table_properties={"dataLayer": "gold"}
)
def sales_gold():
    return (
        dlt.read("sales_silver")
        .groupBy(date_format(col("TransactionDate"), "yyyy-MM-dd").alias("TransactionDate"))
        .agg(
            sum("Amount").alias("TotalAmount"),
            sum("Quantity").alias("TotalQuantity")
        )
    )
```
### Step 3: Create and Configure the DLT Pipeline

1. In the Databricks workspace, navigate to **Data Engineering** > **Create Pipelines**.
2. Configure the pipeline with the following settings:
   - **Pipeline Name**: E.g., `SQLServer-Sales-Pipeline`.
   - **Pipeline Mode**: Choose **Triggered** for batch processing or **Continuous** for streaming (e.g., with CDC).
   - **Notebook Library**: Select the notebook containing the code above.
   - **Destination**: Specify a Unity Catalog schema (e.g., `catalog.schema`) to store Delta tables.
   - **Compute**: Use a **Serverless cluster** (if available) or a cluster with the SQL Server JDBC driver (Databricks Runtime 7.0+).
3. **Optional Settings**:
   - Enable **Auto Optimize** for Delta table performance.
   - Set a **schedule** (e.g., hourly) for incremental runs.
4. Click **Create**.

### Step 4: Run and Monitor

- Click Start to run the pipeline. It will:

    - Create Delta tables (sales_bronze, sales_silver, sales_gold) in the specified schema.
    - Ingest data from dbo.Sales via JDBC.
    - Apply transformations and quality checks.
    - Generate a data lineage graph in the DLT UI.

- Monitor the pipeline in the DLT UI for:
    - Rows processed per layer.
    - Data quality metrics (e.g., rows dropped due to expectations).
    - Errors or performance issues.
### Step 5: Optional Incremental Load
For large tables, avoid full table scans by using incremental loading. Modify the sales_bronze table to filter based on a timestamp (e.g., TransactionDate):
```python
@dlt.table(
    comment="Raw sales data from SQL Server (incremental)",
    table_properties={"dataLayer": "bronze"}
)
def sales_bronze():
    # Example: Fetch rows from the last 7 days
    query = "(SELECT * FROM dbo.Sales WHERE TransactionDate >= DATEADD(day, -7, GETDATE())) sales"
    return (
        spark.read
        .format("jdbc")
        .option("url", jdbc_url)
        .option("dbtable", query)
        .option("fetchsize", "1000")
        .options(**connection_properties)
        .load()
    )
```
### Step 6: Optional Change Data Capture (CDC)
If you need real-time updates from dbo.Sales, enable CDC on SQL Server and modify the pipeline for streaming. First, enable CDC:
```sql
USE SampleDB;
GO
EXEC sys.sp_cdc_enable_db;
EXEC sys.sp_cdc_enable_table @source_schema = 'dbo', @source_name = 'Sales', @role_name = NULL;
```
Then, update the sales_bronze definition to read from the CDC change table:
```python
@dlt.table(
    comment="Raw CDC data from SQL Server",
    table_properties={"dataLayer": "bronze"},
    spark_conf={"spark.databricks.delta.schema.autoMerge.enabled": "true"}
)
def sales_bronze():
    query = "(SELECT * FROM cdc.dbo_Sales_CT WHERE __$start_lsn > {last_lsn}) cdc_data"
    return (
        spark.readStream
        .format("jdbc")
        .option("url", jdbc_url)
        .option("dbtable", query.format(last_lsn="<last_processed_lsn>"))
        .option("fetchsize", "1000")
        .options(**connection_properties)
        .load()
    )
```
Use dlt.apply_changes in the Silver layer to merge CDC updates (as shown in the previous response). Replace <last_processed_lsn> with a mechanism to track the last processed Log Sequence Number (e.g., stored in a Delta table).