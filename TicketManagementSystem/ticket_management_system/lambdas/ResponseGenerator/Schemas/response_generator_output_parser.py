from typing import Dict, List, Optional
from langchain_core.output_parsers import JsonOutputParser
from pydantic import BaseModel, Field


# Response Generator Content Model
class ResponseGeneratorContentDict(BaseModel):
    customer_response: str = Field(description="Your response to the customer")
    priority: str = Field(description="Ticket priority classification: CRITICAL, HIGH, MEDIUM, or NORMAL")
    priority_reasoning: str = Field(description="Brief explanation for the priority classification")


class ResponseGeneratorOutput(BaseModel):
    output: ResponseGeneratorContentDict


response_generator_output_parser = JsonOutputParser(pydantic_object=ResponseGeneratorOutput)