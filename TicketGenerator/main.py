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
project_name=os.getenv("PROJECT_NAME")
# Initialize LLM
llm = ChatBedrock(model_id="us.amazon.nova-lite-v1:0", temperature=0.7, max_tokens=500)

SENTIMENT_WEIGHTS = {
    "NEGATIVE": 0.22,        
    "SLIGHTLY NEGATIVE": 0.28, 
    "NEUTRAL": 0.30,         
    "SLIGHTLY POSITIVE": 0.12, 
    "POSITIVE": 0.08       
}
results = []  # collect ground truth per ticket

for i in range(100):
    sentiment = random.choices(
        list(SENTIMENT_WEIGHTS.keys()),
        weights=list(SENTIMENT_WEIGHTS.values()),
        k=1
    )[0]

    scenario = random.choice(issue_scenarios)
    product = (scenario.get("product"),)
    print(f"Selected Sentiment:{sentiment}")
    print(f"Selected Product:{scenario.get('product')}")
    print(f"Selected issue Type:{scenario.get('issue_type')}")
    print("\n")
    issue_type = scenario.get("issue_type")
    formatted_task = TICKET_GENERATOR_TASK.format(
        sentiment=sentiment,
        product=scenario.get("product"),
        issue_type=scenario.get("issue_type"),
    )

    formatted_guidelines = TICKET_GENERATOR_GUIDELINES.format(sentiment=sentiment)

    prompt_text = PromptTemplate.from_template(TICKET_GENERATOR_TEMPLATE).format(
        task=formatted_task,
        guidelines=formatted_guidelines,
        examples=TICKET_GENERATOR_EXAMPLES,
        format_instructions=ticket_generator_output_parser.get_format_instructions(),
    )
    prompt_messages = [
        ("system", TICKET_GENERATOR_SYSTEM_ROLE),
        (
            "human",
            [{"type": "text", "text": "{prompt_text}"}],
        ),
    ]
    chat_prompt = ChatPromptTemplate.from_messages(prompt_messages)
    chain = chat_prompt | llm | ticket_generator_output_parser
    llm_response = chain.invoke({"prompt_text": prompt_text})

    kinesis = boto3.client(
        "kinesis",
        region_name=os.getenv("AWS_REGION")
    )

    ticket_id=generate_ticket_id()
    submitted_at=get_current_timestamp_str()
    record_payload = {
        "eventName": "TicketSubmitted",
        "ticketId": ticket_id,
        "submittedAt": submitted_at,
        "data": llm_response['output']
    }

    # Send to Kinesis using ticket_id as the partition key
    response = kinesis.put_record(
        StreamName=f"{project_name}-kinesis-stream",
        Data=json.dumps(record_payload).encode("utf-8"),
        PartitionKey=ticket_id
    )
    results.append({
        "ticket_id": ticket_id,
        "sentiment_target": sentiment
    })

with open('results.pkl', 'wb') as f:
    pickle.dump(results, f)

