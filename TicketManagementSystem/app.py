import os
from dotenv import load_dotenv
import aws_cdk as cdk
from aws_cdk import Environment

from ticket_management_system.ticket_management_system_stack import TicketManagementSystemStack

load_dotenv(override=True)

app = cdk.App()

stack =TicketManagementSystemStack(
    app, 
    construct_id="ThesisTestStack",
    env=Environment(
        account=os.getenv("CDK_DEFAULT_ACCOUNT"),
        region=os.getenv("CDK_DEFAULT_REGION")
    ),
    stack_name=f"ThesisTestStack",
    description=f"Stef ThesisTestStack",
)
app.synth()
