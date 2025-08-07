import sys
from awsglue.transforms import *
from awsglue.utils import getResolvedOptions
from pyspark.context import SparkContext
from awsglue.context import GlueContext
from awsglue.dynamicframe import DynamicFrame
from awsglue.job import Job
from pyspark.sql import functions as F
from pyspark.sql.types import *
import boto3

# Get job parameters
args = getResolvedOptions(sys.argv, [
    'JOB_NAME', 
    'S3_BUCKET', 
    'REDSHIFT_CONNECTION',
    'TEMP_DIR'
])

# Initialize Glue context
sc = SparkContext()
glueContext = GlueContext(sc)
spark = glueContext.spark_session
job = Job(glueContext)
job.init(args['JOB_NAME'], args)

print(f"Starting job: {args['JOB_NAME']}")
print(f"Processing tickets from bucket: {args['S3_BUCKET']}")
print(f"Job bookmark enabled: {args.get('job-bookmark-option', 'Not set')}")

try:
    # Define S3 path for tickets
    s3_input_path = f"s3://{args['S3_BUCKET']}/tickets/"
    
    print(f"Reading from S3 path: {s3_input_path}")
    print("Job bookmarks will only process new/modified files since last successful run")
    
    # Create DynamicFrame from S3 with job bookmarks enabled
    # This will automatically track processed files
    tickets_dyf = glueContext.create_dynamic_frame.from_options(
        format_options={"multiline": False},
        connection_type="s3",
        format="json",
        connection_options={
            "paths": [s3_input_path],
            "recurse": True,
            "groupFiles": "inPartition"
        },
        transformation_ctx="tickets_source"  # Required for bookmarks
    )
    
    record_count = tickets_dyf.count()
    print(f"Number of NEW records read (bookmark filtered): {record_count}")
    
    if record_count > 0:
        # Convert to DataFrame for easier processing
        tickets_df = tickets_dyf.toDF()
        
        # Show which files are being processed (for debugging)
        input_files = tickets_df.inputFiles()
        print(f"Processing {len(input_files)} new files:")
        for file_path in input_files[:10]:  # Show first 10 files
            print(f"  - {file_path}")
        if len(input_files) > 10:
            print(f"  ... and {len(input_files) - 10} more files")
        
        # Show schema for debugging
        print("Schema of input data:")
        tickets_df.printSchema()
        
        # Data transformations and cleaning
        processed_df = tickets_df.select(
            F.col("ticket_id").alias("ticket_id"),
            F.col("submitted_at").alias("submitted_at"),
            F.col("customer_name").alias("customer_name"),
            F.col("customer_email").alias("customer_email"),
            F.col("product").alias("product"),
            F.col("issue_type").alias("issue_type"),
            F.col("subject").alias("subject"),
            F.col("description").alias("description"),
            F.col("sentiment").alias("sentiment"),
            F.col("sentiment_score_mixed").cast("double").alias("sentiment_score_mixed"),
            F.col("sentiment_score_negative").cast("double").alias("sentiment_score_negative"),
            F.col("sentiment_score_neutral").cast("double").alias("sentiment_score_neutral"),
            F.col("sentiment_score_positive").cast("double").alias("sentiment_score_positive"),
            F.col("response_text").alias("response_text"),
            F.col("priority").alias("priority"),
            F.col("priority_reasoning").alias("priority_reasoning"),
            F.col("processed_at").alias("processed_at")
        )
        
        # Add data quality checks
        processed_df = processed_df.filter(
            F.col("ticket_id").isNotNull() & 
            F.col("submitted_at").isNotNull()
        )
        
        clean_count = processed_df.count()
        print(f"Records after cleaning: {clean_count}")
        
        if clean_count > 0:
            # Convert back to DynamicFrame for writing
            processed_dyf = DynamicFrame.fromDF(processed_df, glueContext, "processed_tickets")
            
            # Write to Redshift
            print("Writing to Redshift...")
            glueContext.write_dynamic_frame.from_jdbc_conf(
                frame=processed_dyf,
                catalog_connection=args['REDSHIFT_CONNECTION'],
                connection_options={
                    "dbtable": "stef_workspace.processed_tickets",
                    "database": "data"
                },
                redshift_tmp_dir=args['TEMP_DIR'],
                transformation_ctx="redshift_sink"  # Required for bookmarks
            )
            
            print(f"Successfully processed {clean_count} NEW tickets to Redshift")
        else:
            print("No records passed data quality checks")
        
    else:
        print("No new tickets to process - all files already processed by previous job runs")

except Exception as e:
    print(f"Error processing tickets: {str(e)}")
    import traceback
    traceback.print_exc()
    raise e

finally:
    # Commit job to update bookmark - this marks current files as processed
    job.commit()
    print("Job completed successfully - bookmark updated")