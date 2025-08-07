import base64
import json
import os
import boto3

sfn = boto3.client("stepfunctions")
SFN_ARN = os.environ["SFN_ARN"]

def lambda_handler(event, context):
    try:
        # Process each record from the Kinesis stream
        for record in event["Records"]:
            # Decode the Kinesis data payload (it's base64 encoded)
            payload = base64.b64decode(record["kinesis"]["data"]).decode("utf-8")
            data = json.loads(payload)
            
            # Start Step Functions execution
            sfn.start_execution(
                stateMachineArn=SFN_ARN,
                input=json.dumps({"ticket": data})
            )

    except Exception as e:
        # Log and raise error to make Lambda fail
        print(f"Error processing records: {str(e)}")
        raise

    return {
        "statusCode": 200,
        "body": json.dumps("Lambda processed Kinesis event successfully."),
    }
