import aws_cdk as core
import aws_cdk.assertions as assertions

from ticket_management_system.ticket_management_system_stack import TicketManagementSystemStack

# example tests. To run these tests, uncomment this file along with the example
# resource in ticket_management_system/ticket_management_system_stack.py
def test_sqs_queue_created():
    app = core.App()
    stack = TicketManagementSystemStack(app, "ticket-management-system")
    template = assertions.Template.from_stack(stack)

#     template.has_resource_properties("AWS::SQS::Queue", {
#         "VisibilityTimeout": 300
#     })
