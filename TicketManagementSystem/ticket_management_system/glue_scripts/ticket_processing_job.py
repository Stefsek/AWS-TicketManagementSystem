import sys
from awsglue.transforms import *
from awsglue.utils import getResolvedOptions
from pyspark.context import SparkContext
from awsglue.context import GlueContext
from awsglue.dynamicframe import DynamicFrame
from awsglue.job import Job
from pyspark.sql import functions as F
from pyspark.sql.types import *

def get_ticket_schema():
    """
    Define the schema mapping for ticket data processing.
    
    Returns:
        list: List of tuples containing (column_name, spark_data_type) pairs
              for all ticket fields including sentiment scores and timestamps.
    """
    return [
        ("ticket_id", StringType()),
        ("submitted_at", TimestampType()),
        ("customer_first_name", StringType()),
        ("customer_last_name", StringType()),
        ("customer_full_name", StringType()),
        ("customer_email", StringType()),
        ("product", StringType()),
        ("issue_type", StringType()),
        ("subject", StringType()),
        ("description", StringType()),
        ("sentiment", StringType()),
        ("sentiment_score_mixed", DoubleType()),
        ("sentiment_score_negative", DoubleType()),
        ("sentiment_score_neutral", DoubleType()),
        ("sentiment_score_positive", DoubleType()),
        ("response_text", StringType()),
        ("priority", StringType()),
        ("priority_reasoning", StringType()),
        ("processed_at", TimestampType())
    ]

def read_tickets_from_s3(glue_context, s3_bucket):
    """
    Extract ticket JSON data from S3 bucket using AWS Glue.
    
    Args:
        glue_context (GlueContext): AWS Glue context for data operations
        s3_bucket (str): Name of the S3 bucket containing ticket data
        
    Returns:
        DynamicFrame: Glue DynamicFrame containing all ticket records from
                     s3://{bucket}/tickets/ with recursive file discovery
                     
    Raises:
        Exception: If S3 path is inaccessible or JSON format is invalid
    """
    s3_input_path = f"s3://{s3_bucket}/tickets/"
    
    return glue_context.create_dynamic_frame.from_options(
        format_options={"multiline": False},
        connection_type="s3",
        format="json",
        connection_options={
            "paths": [s3_input_path],
            "recurse": True,
            "groupFiles": "inPartition"
        },
        transformation_ctx="tickets_source"
    )

def apply_schema_casting(df, schema):
    """
    Transform DataFrame columns to match target Redshift schema types.
    
    Args:
        df (DataFrame): Input Spark DataFrame with raw ticket data
        schema (list): List of (column_name, data_type) tuples from get_ticket_schema()
        
    Returns:
        DataFrame: Transformed DataFrame with properly typed columns for Redshift.
                  Sentiment scores cast to DoubleType, timestamps to TimestampType.
                  
    Note:
        Only casts columns that exist in the DataFrame. Missing columns are ignored.
    """
    for col_name, col_type in schema:
        if col_name in df.columns:
            df = df.withColumn(col_name, F.col(col_name).cast(col_type))
    return df

def validate_no_nulls(df, schema):
    """
    Perform data quality validation to ensure no null values exist.
    
    Args:
        df (DataFrame): Spark DataFrame to validate
        schema (list): Schema definition to check all required columns
        
    Returns:
        bool: True if validation passes
        
    Raises:
        ValueError: If any column contains null values. Error message includes
                   detailed breakdown of null counts per column.
                   
    Example:
        ValueError: "Data quality check failed! Found 5 null values across 
                    columns: {'customer_name': 2, 'product': 3}"
    """
    print("Checking for null values...")
    null_counts = {}
    
    for col_name, _ in schema:
        if col_name in df.columns:
            null_count = df.filter(F.col(col_name).isNull()).count()
            null_counts[col_name] = null_count
            if null_count > 0:
                print(f"Column '{col_name}' has {null_count} null values")
    
    total_nulls = sum(null_counts.values())
    if total_nulls > 0:
        error_msg = f"Data quality check failed! Found {total_nulls} null values across columns: {null_counts}"
        raise ValueError(error_msg)
    
    print("All columns passed null validation ✓")
    return True

def write_to_redshift(glue_context, df, connection_name, database, schema, table, temp_dir):
    """
    Load processed ticket data into Redshift table using JDBC connection.
    
    Args:
        glue_context (GlueContext): AWS Glue context for Redshift operations
        df (DataFrame): Validated and transformed ticket DataFrame
        connection_name (str): Name of Glue connection to Redshift cluster
        database (str): Redshift database name
        schema (str): Redshift schema name
        table (str): Redshift table name
        temp_dir (str): S3 path for temporary staging during Redshift load
        
    Raises:
        Exception: If Redshift connection fails, table doesn't exist, or
                  data type mismatches occur during insert operation
                  
    Note:
        Uses COPY command via S3 staging for optimal performance.
    """
    processed_dyf = DynamicFrame.fromDF(df, glue_context, "processed_tickets")
    
    # Construct fully qualified table name
    full_table_name = f"{schema}.{table}"
    
    print(f"Writing to Redshift table: {database}.{full_table_name}")
    
    glue_context.write_dynamic_frame.from_jdbc_conf(
        frame=processed_dyf,
        catalog_connection=connection_name,
        connection_options={
            "dbtable": full_table_name,
            "database": database
        },
        redshift_tmp_dir=temp_dir,
        transformation_ctx="redshift_sink"
    )

def process_tickets(args, glue_context):
    """
    Execute the complete ETL pipeline for ticket data processing.
    
    Pipeline stages:
    1. Extract: Read JSON tickets from S3
    2. Transform: Apply schema casting and data validation
    3. Load: Write validated data to Redshift
    
    Args:
        args (dict): Job parameters including S3_BUCKET, REDSHIFT_* configs, TEMP_DIR
        glue_context (GlueContext): AWS Glue context for all operations
        
    Raises:
        ValueError: If data quality validation fails (null values found)
        Exception: If any ETL stage fails (S3 read, transformation, Redshift write)
        
    Returns:
        None: Prints progress messages and record counts to CloudWatch logs
    """
    schema = get_ticket_schema()

    # Read data from S3
    tickets_dyf = read_tickets_from_s3(glue_context, args['S3_BUCKET'])
    record_count = tickets_dyf.count()
    if record_count == 0:
        print("No tickets to process")
        return
    
    # Convert to DataFrame and apply transformations
    tickets_df = tickets_dyf.toDF()
    tickets_df = apply_schema_casting(tickets_df, schema)
    
    # Validate data quality
    validate_no_nulls(tickets_df, schema)
    
    print(f"Records to process: {tickets_df.count()}")
    
    # Write to Redshift
    print("Writing to Redshift...")
    write_to_redshift(
        glue_context=glue_context,
        df=tickets_df,
        connection_name=args['REDSHIFT_CONNECTION'],
        database=args['REDSHIFT_DATABASE'],
        schema=args['REDSHIFT_SCHEMA'],
        table=args['REDSHIFT_TABLE'],
        temp_dir=args['TEMP_DIR']
    )
    
    print(f"Successfully processed {tickets_df.count()} tickets to {args['REDSHIFT_SCHEMA']}.{args['REDSHIFT_TABLE']}")


args = getResolvedOptions(sys.argv, [
    'JOB_NAME', 
    'S3_BUCKET', 
    'REDSHIFT_DATABASE',
    'REDSHIFT_SCHEMA',
    'REDSHIFT_TABLE',
    'REDSHIFT_CONNECTION',
    'TEMP_DIR'
])

# Initialize Glue context
sc = SparkContext()
glue_context = GlueContext(sc)
spark = glue_context.spark_session
job = Job(glue_context)
job.init(args['JOB_NAME'], args)

print(f"Starting job: {args['JOB_NAME']}")

try:
    process_tickets(args, glue_context)
except Exception as e:
    print(f"Error processing tickets: {str(e)}")
    raise e
finally:
    job.commit()
    print("Job completed successfully")