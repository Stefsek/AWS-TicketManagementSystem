import random
import os
import boto3
import pickle
import time
import json
from dotenv import load_dotenv
from langchain_aws import ChatBedrock
from langchain_core.prompts import ChatPromptTemplate, PromptTemplate

from IssueScenarios.issue_scenarios import issue_scenarios
from Prompts.ticket_generator_prompts import *
from Schemas.ticket_generator_output_parser import ticket_generator_output_parser
from Utils.ticked_id_generator import generate_ticket_id
from Utils.timestamp import get_current_timestamp_str
from pprint import pprint

load_dotenv(override=True)

# Load project name from environment variables
project_name = os.getenv("PROJECT_NAME")

# Initialize LLM with chosen model, temperature, and max token length
llm = ChatBedrock(model_id="us.amazon.nova-lite-v1:0", temperature=0.7, max_tokens=500)

# Define sentiment weights (used to randomly assign a sentiment to the ticket)
SENTIMENT_WEIGHTS = {
    "NEGATIVE": 0.22,
    "SLIGHTLY NEGATIVE": 0.28,
    "NEUTRAL": 0.30,
    "SLIGHTLY POSITIVE": 0.12,
    "POSITIVE": 0.08
}

# Randomly select one sentiment based on weights
sentiment = random.choices(
    list(SENTIMENT_WEIGHTS.keys()),
    weights=list(SENTIMENT_WEIGHTS.values()),
    k=1
)[0]

# Randomly pick one issue scenario
scenario = random.choice(issue_scenarios)

# Debug info: print selected attributes
print(f"Selected Sentiment: {sentiment}")
print(f"Selected Product: {scenario.get('product')}")
print(f"Selected Issue Type: {scenario.get('issue_type')}")
print("\n")

# Extract issue type
issue_type = scenario.get("issue_type")

# Format the task prompt with chosen sentiment, product, and issue type
formatted_task = TICKET_GENERATOR_TASK.format(
    sentiment=sentiment,
    product=scenario.get("product"),
    issue_type=issue_type,
)

# Format guidelines with chosen sentiment
formatted_guidelines = TICKET_GENERATOR_GUIDELINES.format(sentiment=sentiment)

# Build the full prompt for the LLM
prompt_text = PromptTemplate.from_template(TICKET_GENERATOR_TEMPLATE).format(
    task=formatted_task,
    guidelines=formatted_guidelines,
    examples=TICKET_GENERATOR_EXAMPLES,
    format_instructions=ticket_generator_output_parser.get_format_instructions(),
)

# Define system + human roles for the conversation
prompt_messages = [
    ("system", TICKET_GENERATOR_SYSTEM_ROLE),
    (
        "human",
        [{"type": "text", "text": "{prompt_text}"}],  # placeholder for actual prompt text
    ),
]

# Build LangChain pipeline: prompt → LLM → parser
chat_prompt = ChatPromptTemplate.from_messages(prompt_messages)
chain = chat_prompt | llm | ticket_generator_output_parser

# Run the chain and get generated ticket response
llm_response = chain.invoke({"prompt_text": prompt_text})

# Initialize Kinesis client
kinesis = boto3.client(
    "kinesis",
    region_name=os.getenv("AWS_REGION")
)

# Generate unique ticket ID and timestamp
ticket_id = generate_ticket_id()
submitted_at = get_current_timestamp_str()

# Build payload to send to Kinesis
record_payload = {
    "eventName": "TicketSubmitted",
    "ticketId": ticket_id,
    "submittedAt": submitted_at,
    "data": llm_response['output']
}

# Send record to Kinesis stream (partitioned by ticket_id)
response = kinesis.put_record(
    StreamName=f"{project_name}-kinesis-stream",
    Data=json.dumps(record_payload).encode("utf-8"),
    PartitionKey=ticket_id
)
