import random
import os
import boto3
import pickle
import time
import json
from dotenv import load_dotenv
from langchain_aws import ChatBedrock
from langchain_core.prompts import ChatPromptTemplate, PromptTemplate

from Prompts.ticket_response_evaluator_prompts import *
from Schemas.ticket_response_evaluator_output_parser import ticket_response_evaluation_parser
from pprint import pprint


# Path to your JSONL file
file_path = "ProcessedTickets/processed_tickets000.json"

# Read JSON objects from the file
tickets = []
with open(file_path, "r", encoding="utf-8") as f:
    for line in f:
        line = line.strip()
        if line:  # skip empty lines
            tickets.append(json.loads(line))

llm = ChatBedrock(model_id="us.amazon.nova-pro-v1:0", temperature=0.2, max_tokens=200)
evals=[]
# Example: iterate and prepare evaluator prompt inputs
for ticket in tickets:
    ticket_subject = ticket["subject"]
    ticket_description = ticket["description"]
    response_text = ticket["response_text"]
    
    prompt_text = PromptTemplate.from_template(TICKET_RESPONSE_EVALUATOR_TEMPLATE).format(
        task=TICKET_RESPONSE_EVALUATOR_TASK,
        ticket_subject=ticket_subject,
        ticket_description=ticket_description,
        response_text = response_text,
        guidelines=TICKET_RESPONSE_EVALUATOR_GUIDELINES,
        examples=TICKET_RESPONSE_EVALUATOR_EXAMPLES,
        format_instructions=ticket_response_evaluation_parser.get_format_instructions(),
    )
    prompt_messages = [
        ("system", TICKET_RESPONSE_EVALUATOR_SYSTEM_ROLE),
        (
            "human",
            [{"type": "text", "text": "{prompt_text}"}],
        ),
    ]
    chat_prompt = ChatPromptTemplate.from_messages(prompt_messages)
    chain = chat_prompt | llm | ticket_response_evaluation_parser
    llm_response = chain.invoke({"prompt_text": prompt_text})
    print(llm_response['output'])
    evals.append(llm_response['output'])
with open("ticket_evaluations.pkl", "wb") as f:
    pickle.dump(evals, f)