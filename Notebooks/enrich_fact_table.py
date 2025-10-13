from pyspark.sql import SparkSession
from pyspark.sql.functions import col

def enrich_fact_table(fact_table_name: str, lookup_table_name: str, join_key: str, new_column: str, join_type: str = "left"):
    """
    Generic method to join a fact table with a lookup table and add a new column to the fact table.
    
    Parameters:
    - fact_table_name (str): Name of the fact table (e.g., 'fact_table').
    - lookup_table_name (str): Name of the lookup table (e.g., 'lookup_table').
    - join_key (str): Column name to join on (must exist in both tables).
    - new_column (str): Column from the lookup table to add to the fact table.
    - join_type (str): Type of join ('left', 'inner', 'right', etc.). Default is 'left'.
    
    Returns:
    - DataFrame: Fact table with all original columns plus the new column from the lookup table.
    """
    # Initialize Spark session
    spark = SparkSession.builder.appName("EnrichFactTable").getOrCreate()
    
    try:
        # Load the fact and lookup tables as DataFrames
        fact_df = spark.table(fact_table_name)
        lookup_df = spark.table(lookup_table_name)
        
        # Verify that the join key exists in both tables
        if join_key not in fact_df.columns or join_key not in lookup_df.columns:
            raise ValueError(f"Join key '{join_key}' not found in one or both tables.")
        
        # Verify that the new column exists in the lookup table
        if new_column not in lookup_df.columns:
            raise ValueError(f"Column '{new_column}' not found in lookup table '{lookup_table_name}'.")
        
        # Perform the join and select all columns from fact table plus the new column
        enriched_df = fact_df.join(
            lookup_df,
            fact_df[join_key] == lookup_df[join_key],
            join_type
        ).select(
            fact_df["*"],  # Select all columns from fact table
            lookup_df[new_column].alias(new_column)  # Add the new column
        )
        
        return enriched_df
    
    except Exception as e:
        print(f"Error: {str(e)}")
        return None
        
enriched_df = enrich_fact_table(
    fact_table_name="fact_table",
    lookup_table_name="lookup_table",
    join_key="id",
    new_column="lookup_name",
    join_type="left"
)

# Show the result
if enriched_df:
    enriched_df.show()
    
    # Optionally, save the result to a new table
    enriched_df.write.format("delta").mode("overwrite").saveAsTable("fact_table_enriched")