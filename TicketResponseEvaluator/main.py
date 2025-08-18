import pickle
import json
from langchain_aws import ChatBedrock
from langchain_core.prompts import ChatPromptTemplate, PromptTemplate

from Prompts.ticket_response_evaluator_prompts import *
from Schemas.ticket_response_evaluator_output_parser import ticket_response_evaluation_parser


file_path = "ProcessedTickets/processed_tickets000.json"

# List to hold all tickets loaded from the file
tickets = []
with open(file_path, "r", encoding="utf-8") as f:
    for line in f:
        line = line.strip()
        if line:  # Ignore empty lines
            tickets.append(json.loads(line))  # Parse each line as JSON

# Initialize the Bedrock model with given parameters
llm = ChatBedrock(model_id="us.amazon.nova-pro-v1:0", temperature=0.2, max_tokens=200)

# Store evaluation results for each ticket
evals = []

# Process each ticket one by one
for ticket in tickets:
    ticket_subject = ticket["subject"]
    ticket_description = ticket["description"]
    response_text = ticket["response_text"]
    
    # Build the evaluator prompt by filling the template with ticket data
    prompt_text = PromptTemplate.from_template(TICKET_RESPONSE_EVALUATOR_TEMPLATE).format(
        task=TICKET_RESPONSE_EVALUATOR_TASK,
        ticket_subject=ticket_subject,
        ticket_description=ticket_description,
        response_text=response_text,
        guidelines=TICKET_RESPONSE_EVALUATOR_GUIDELINES,
        examples=TICKET_RESPONSE_EVALUATOR_EXAMPLES,
        format_instructions=ticket_response_evaluation_parser.get_format_instructions(),
    )

    # Define the conversation structure for the LLM
    prompt_messages = [
        ("system", TICKET_RESPONSE_EVALUATOR_SYSTEM_ROLE),
        (
            "human",
            [{"type": "text", "text": "{prompt_text}"}],  # Placeholder for actual prompt text
        ),
    ]

    # Create a chain: prompt → LLM → parser
    chat_prompt = ChatPromptTemplate.from_messages(prompt_messages)
    chain = chat_prompt | llm | ticket_response_evaluation_parser

    # Run the evaluation for the current ticket
    llm_response = chain.invoke({"prompt_text": prompt_text})

    # Print the structured evaluation result
    print(llm_response['output'])

    # Collect results in a list
    evals.append(llm_response['output'])

# Save all evaluations into a file for later use
with open("Evals/ticket_evaluations.pkl", "wb") as f:
    pickle.dump(evals, f)