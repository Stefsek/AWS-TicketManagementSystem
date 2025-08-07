from Prompts.response_generator_prompts import (
    RESPONSE_GENERATOR_TASK,
    RESPONSE_GENERATOR_GUIDELINES,
    RESPONSE_GENERATOR_EXAMPLES,
    RESPONSE_GENERATOR_TEMPLATE,
    RESPONSE_GENERATOR_SYSTEM_ROLE,
)
from langchain_core.prompts import PromptTemplate, ChatPromptTemplate
from langchain_aws import ChatBedrock
from Schemas.response_generator_output_parser import response_generator_output_parser


class TicketResponseGenerator:
    """
    Encapsulates prompt formatting and LLM interaction for generating ticket responses.
    """

    def __init__(
        self,
        model_id: str = "us.amazon.nova-pro-v1:0",
        temperature: float = 0.7,
        max_tokens: int = 1000,
    ):
        # Initialize the Bedrock LLM client
        self.llm = ChatBedrock(
            model_id=model_id,
            temperature=temperature,
            max_tokens=max_tokens,
        )

    def format_prompt(self, **kwargs) -> str:
        """
        Formats the system task, guidelines, and examples into a single prompt text.

        Expects flat keyword arguments:
        - subject: str
        - description: str
        - customer_name: str
        - company: str
        - sentiment: str = "NEUTRAL"
        - product: str
        - issue_type: str
        - ticket_id: str

        Returns:
            A fully formatted prompt string ready for the LLM.
        """
        subject = kwargs.get("subject", "")
        description = kwargs.get("description", "")
        customer_name = kwargs.get("customer_name", "")
        company = kwargs.get("company", "")
        sentiment = kwargs.get("sentiment", "NEUTRAL")
        product = kwargs.get("product", "")
        issue_type = kwargs.get("issue_type", "")
        ticket_id = kwargs.get("ticket_id", "")

        formatted_task = RESPONSE_GENERATOR_TASK.format(
            subject=subject,
            description=description,
            customer_name=customer_name,
            company=company,
            sentiment=sentiment,
            product=product,
            issue_type=issue_type,
        )
        formatted_guidelines = RESPONSE_GENERATOR_GUIDELINES.format(
            company=company,
            product=product,
            issue_type=issue_type,
        )
        formatted_examples = RESPONSE_GENERATOR_EXAMPLES.format(
            ticket_id=ticket_id
        )

        prompt_text = PromptTemplate.from_template(RESPONSE_GENERATOR_TEMPLATE).format(
            task=formatted_task,
            guidelines=formatted_guidelines,
            examples=formatted_examples,
            format_instructions=response_generator_output_parser.get_format_instructions(),
        )
        return prompt_text

    def generate_response(self, **kwargs) -> str:
        """
        Builds the chat prompt, invokes the LLM, and parses the output.

        Accepts the same kwargs as format_prompt.

        Returns:
            The generated ticket response text.
        """
        prompt_text = self.format_prompt(**kwargs)
        # Prepare chat messages
        prompt_messages = [
            ("system", RESPONSE_GENERATOR_SYSTEM_ROLE),
            (
                "human",
                [{"type": "text", "text": "{prompt_text}"}],
            ),
        ]
        # Create a chat prompt template
        chat_prompt = ChatPromptTemplate.from_messages(prompt_messages)

        # Compose the chain: prompt -> llm -> parser
        chain = chat_prompt | self.llm | response_generator_output_parser
        result = chain.invoke({"prompt_text": prompt_text})

        # Extract and return the response
        return result["output"]