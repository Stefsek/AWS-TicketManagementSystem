import boto3
import json
import os
from datetime import datetime

s3 = boto3.client('s3')

def lambda_handler(event, context):
    bucket_name = os.environ['S3_BUCKET_NAME']
    
    try:
        # Extract data from Step Functions payload
        ticket_data = event.get('ticket', {})
        comprehend_result = event.get('ComprehendResult', {})
        response_generator = event.get('ResponseGenerator', {}).get('Payload', {})

        processed_at_dt = datetime.utcnow()
        processed_at_str = processed_at_dt.isoformat()

        # Transform to clean JSON structure with flattened sentiment scores
        transformed_ticket = {
            'ticket_id': ticket_data.get('ticketId'),
            'submitted_at': ticket_data.get('submittedAt'),
            'customer_first_name': ticket_data.get('data', {}).get('customer_contact_information', {}).get('first_name'),
            'customer_last_name': ticket_data.get('data', {}).get('customer_contact_information', {}).get('last_name'),
            'customer_full_name': ticket_data.get('data', {}).get('customer_contact_information', {}).get('full_name'),
            'customer_email': ticket_data.get('data', {}).get('customer_contact_information', {}).get('email'),
            'product': ticket_data.get('data', {}).get('product_issue_information', {}).get('product'),
            'issue_type': ticket_data.get('data', {}).get('product_issue_information', {}).get('issue_type'),
            'subject': ticket_data.get('data', {}).get('subject'),
            'description': ticket_data.get('data', {}).get('description'),
            'response_text': response_generator.get('response'),
            'sentiment': comprehend_result.get('Sentiment'),
            'sentiment_score_mixed': comprehend_result.get('SentimentScore', {}).get('Mixed', 0),
            'sentiment_score_negative': comprehend_result.get('SentimentScore', {}).get('Negative', 0),
            'sentiment_score_neutral': comprehend_result.get('SentimentScore', {}).get('Neutral', 0),
            'sentiment_score_positive': comprehend_result.get('SentimentScore', {}).get('Positive', 0),
            'priority': response_generator.get('priority'),
            'priority_reasoning': response_generator.get('priority_reasoning'),
            'processed_at': processed_at_str
        }

        s3_key = f"tickets/{processed_at_dt.year}/{processed_at_dt.month:02d}/{processed_at_dt.day:02d}/ticket_{transformed_ticket['ticket_id']}.json"
        
        # Save to S3
        s3.put_object(
            Bucket=bucket_name,
            Key=s3_key,
            Body=json.dumps(transformed_ticket, indent=2),
            ContentType='application/json'
        )
        
        print(f"Successfully saved ticket {transformed_ticket['ticket_id']} to S3: {s3_key}")
        
        return {
            'statusCode': 200,
            'ticket_id': transformed_ticket['ticket_id'],
            's3_location': f"s3://{bucket_name}/{s3_key}",
            'message': 'Ticket successfully saved to S3'
        }
        
    except Exception as e:
        print(f"Error processing ticket: {str(e)}")
        raise