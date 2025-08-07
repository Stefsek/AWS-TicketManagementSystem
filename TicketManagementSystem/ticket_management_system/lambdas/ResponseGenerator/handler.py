from Utils.help_functions import extract_ticket_info
from Model.response_generator import TicketResponseGenerator

response_generator = TicketResponseGenerator()

def lambda_handler(event, context):
    try:

        # Extract and flatten the ticket info
        info = extract_ticket_info(event)
        # Generate the LLM response
        llm_output = response_generator.generate_response(**info)
        
        # Success: statusCode 200, plain dict
        return {
            "statusCode": 200,
            "response": llm_output["customer_response"],
            "priority": llm_output["priority"],
            "priority_reasoning":llm_output["priority_reasoning"]
        }

    except Exception as e:
        print(f"Error in lambda_handler: {str(e)}")
        raise
