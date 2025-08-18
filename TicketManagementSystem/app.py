import os
from dotenv import load_dotenv
import aws_cdk as cdk
from aws_cdk import Environment

from ticket_management_system.ticket_management_system_stack import TicketManagementSystemStack

# Load .env configuration (override system env vars if already present)
load_dotenv(override=True)

# Create the CDK app container
app = cdk.App()

# Read project name from environment variables
project_name = os.getenv("PROJECT_NAME")
if not project_name:
    raise ValueError("Missing required environment variable: PROJECT_NAME")

# Instantiate the custom stack
stack = TicketManagementSystemStack(
    scope=app,
    construct_id=f"{project_name}Stack",
    env=Environment(
        account=os.getenv("CDK_DEFAULT_ACCOUNT"),  # AWS Account ID
        region=os.getenv("CDK_DEFAULT_REGION"),    # AWS Region
    ),
    stack_name=f"{project_name}-stack",
    description="AWS real-time ticket management system",  # Shown in CloudFormation console
)

# Synthesize the CloudFormation template
app.synth()
