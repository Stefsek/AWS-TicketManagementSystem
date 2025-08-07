import os
from dotenv import load_dotenv
import aws_cdk as cdk
from aws_cdk import Environment

from ticket_management_system.ticket_management_system_stack import TicketManagementSystemStack

load_dotenv(override=True)

app = cdk.App()
project_name = os.getenv("PROJECT_NAME")
stack =TicketManagementSystemStack(
    app, 
    construct_id=f"{project_name}Stack",
    env=Environment(
        account=os.getenv("CDK_DEFAULT_ACCOUNT"),
        region=os.getenv("CDK_DEFAULT_REGION")
    ),
    stack_name=f"{project_name}-stack",
    description=f"AWS real time ticket management system",
)
app.synth()
