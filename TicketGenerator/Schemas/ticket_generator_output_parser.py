from typing import Dict, List, Optional

from langchain_core.output_parsers import JsonOutputParser
from pydantic import BaseModel, Field


# Customer Contact Information Model
class CustomerContactInfo(BaseModel):
    first_name: str = Field(description="Customer's first name")
    last_name: str = Field(description="Customer's first name")
    full_name: str = Field(description="Customer's full name")
    email: str = Field(description="Customer's email address")
    company: str = Field(description="Customer's company name")


# Product Issue Information Model
class ProductIssueInfo(BaseModel):
    product: str = Field(
        description="AWS product or service name that the ticket is about"
    )
    issue_type: str = Field(description="Type of issue being reported")


# Ticket Output Parser
class TicketGeneratorContentDict(BaseModel):
    subject: str = Field(description="Clear subject line describing the issue")
    description: str = Field(
        description="Detailed description of the issue (100-200 words)"
    )
    customer_contact_information: CustomerContactInfo = Field(
        description="Customer contact information including name, email, and company"
    )
    product_issue_information: ProductIssueInfo = Field(
        description="Information about the AWS product and issue type"
    )


class TicketGeneratorOutput(BaseModel):
    output: TicketGeneratorContentDict


ticket_generator_output_parser = JsonOutputParser(pydantic_object=TicketGeneratorOutput)
