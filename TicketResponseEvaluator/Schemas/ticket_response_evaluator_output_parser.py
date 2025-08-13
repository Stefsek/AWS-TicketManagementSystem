from typing import Dict
from langchain_core.output_parsers import JsonOutputParser
from pydantic import BaseModel, Field

# ---- Evaluation Schema ----
class TicketResponseEvaluation(BaseModel):
    contextual_relevance: bool = Field(
        description="True if the response explicitly acknowledges and addresses the exact AWS service and specific problem described in the ticket, with no unrelated or generic content."
    )
    technical_accuracy: bool = Field(
        description="True if all AWS-related details (service names, parameters, console paths, CLI/API usage, and troubleshooting steps) are factually correct, safe, and directly applicable to the reported issue."
    )
    professional_tone: bool = Field(
        description="True if the response uses a clear, polite, and formal tone consistent with AWS support standards, avoiding slang, emojis, informal expressions, or contractions."
    )
    actionable_guidance: bool = Field(
        description="True if the response contains two to three specific, immediately executable troubleshooting steps that the customer can perform without ambiguity."
    )
class TicketResponseEvaluationOutput(BaseModel):
    output: TicketResponseEvaluation

ticket_response_evaluation_parser = JsonOutputParser(
    pydantic_object=TicketResponseEvaluationOutput
)
