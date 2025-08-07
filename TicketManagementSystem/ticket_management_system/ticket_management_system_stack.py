import os
import pathlib

from aws_cdk import (
    Stack,
    Duration,
    RemovalPolicy,
    aws_kinesis as kinesis,
    aws_lambda as _lambda,
    aws_iam as iam,
    aws_stepfunctions as sfn,
    aws_dynamodb as dynamodb,
    aws_s3 as s3,
    aws_sns as sns,
    aws_sns_subscriptions as subs,
    aws_glue as glue,
    aws_events as events,
    aws_events_targets as targets,
    aws_s3_deployment as s3deploy,
    aws_cloudwatch as cloudwatch,
    aws_cloudwatch_actions as cw_actions
)
from aws_cdk.aws_lambda import CfnEventSourceMapping
from constructs import Construct
from dotenv import load_dotenv

class TicketManagementSystemStack(Stack):
    """
    AWS CDK Stack to provision a complete ticket management system for Sekis Stefanos thesis project.

    This stack orchestrates the following components:
    1. Kinesis Data Stream for ticket ingestion
    2. Lambda functions for event triggering, response generation, and S3 writing
    3. DynamoDB table for tracking ticket metadata
    4. S3 bucket for storing ticket data and generated responses
    5. SNS topic for notifications and alarms
    6. AWS Glue job with EventBridge schedule for ETL into Redshift
    7. Step Functions state machine to handle ticket processing workflows
    8. CloudWatch alarm on Step Function failures

    Environment variables for Redshift connectivity and networking are read from a .env file.
    All resources are set to be destroyed on stack deletion
    """
    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        """
        Initialize the CDK stack and provision all resources.

        Args:
            scope (Construct): The construct within which this stack is defined.
            construct_id (str): Unique identifier for this stack.
            **kwargs: Additional keyword arguments passed to the Stack constructor.
        """
        super().__init__(scope, construct_id, **kwargs)

        # Load configuration and provision resources
        self._unpack_env_params()
        self._create_kinesis_stream()
        self._create_event_trigger_lambda()
        self._create_response_generator_lambda()
        self._create_dynamodb_table()
        self._create_s3_bucket()
        self._create_s3_writer_lambda()
        self._create_sns_topic()
        self._create_glue_job_and_schedule()
        self._create_step_function()
        self._create_failure_alarm()
    

    def _unpack_env_params(self) -> None:
        """
        Load and validate environment variables from .env file for Redshift and networking.

        Reads the following variables:
        - REDSHIFT_JDBC_CONNECTION_URL, REDSHIFT_ARN, REDSHIFT_USERNAME, REDSHIFT_PASSWORD
        - REDSHIFT_DATABASE, REDSHIFT_SCHEMA, REDSHIFT_TABLE
        - REDSHIFT_SUBNET_ID, REDSHIFT_SECURITY_GROUP_ID, AVAILABILITY_ZONE

        Raises:
            ValueError: If any required environment variable is missing.
        """
        load_dotenv()
        required = [
            "REDSHIFT_JDBC_CONNECTION_URL",
            "REDSHIFT_ARN",
            "REDSHIFT_USERNAME",
            "REDSHIFT_PASSWORD",
            "REDSHIFT_DATABASE",
            "REDSHIFT_SCHEMA",
            "REDSHIFT_TABLE",
            "REDSHIFT_SUBNET_ID",
            "REDSHIFT_SECURITY_GROUP_ID",
            "AVAILABILITY_ZONE",
        ]
        missing = [var for var in required if not os.getenv(var)]
        if missing:
            raise ValueError(f"Missing required environment variables: {', '.join(missing)}")

        # Assign to instance variables
        self.redshift_jdbc_url = os.getenv("REDSHIFT_JDBC_CONNECTION_URL")
        self.redshift_arn = os.getenv("REDSHIFT_ARN")
        self.redshift_username = os.getenv("REDSHIFT_USERNAME")
        self.redshift_password = os.getenv("REDSHIFT_PASSWORD")
        self.redshift_database = os.getenv("REDSHIFT_DATABASE")
        self.redshift_schema = os.getenv("REDSHIFT_SCHEMA")
        self.redshift_table = os.getenv("REDSHIFT_TABLE")
        self.redshift_subnet_id = os.getenv("REDSHIFT_SUBNET_ID")
        self.redshift_security_group_id = os.getenv("REDSHIFT_SECURITY_GROUP_ID")
        self.availability_zone = os.getenv("AVAILABILITY_ZONE")
        self.notification_emails = os.getenv("NOTIFICATION_EMAILS")
        emails = os.getenv("NOTIFICATION_EMAILS")
        self.notification_emails = [e.strip() for e in emails.split(",") if e.strip()]

    def _create_kinesis_stream(self) -> None:
        """
        Creates a Kinesis Data Stream for ingesting incoming ticket events.

        Stream configuration:
          - Shard count: 1
          - Retention period: 24 hours
          - Destruction on stack removal
        """
        self.ticket_stream = kinesis.Stream(
            self,
            "ThesisTicketStream",
            stream_name="thesis-ticket-stream",
            shard_count=1,
            retention_period=Duration.hours(24),
        )

        self.ticket_stream.apply_removal_policy(RemovalPolicy.DESTROY)

    def _create_event_trigger_lambda(self) -> None:
        """
        Deploy a Lambda function that listens to the Kinesis stream,
        filters for TicketSubmitted events, and starts the Step Functions
        workflow.

        - Creates an IAM role with:
          • AWSLambdaBasicExecutionRole
          • Permissions to read from the Kinesis stream
          • Permission to call states:StartExecution on our SFN
        - Packages the Lambda from `lambdas/TriggerSFN`
        - Configures an EventSourceMapping with a JSON filter
        """
        # IAM Role for the Lambda to access Kinesis
        self.event_trigger_role = iam.Role(
            self,
            "ThesisTicketProcessorRole",
            assumed_by=iam.ServicePrincipal("lambda.amazonaws.com"),
            role_name="ThesisTicketProcessorRole"
        )
        # Attach basic execution policy
        self.event_trigger_role.add_managed_policy(
            iam.ManagedPolicy.from_aws_managed_policy_name(
                "service-role/AWSLambdaBasicExecutionRole"
            )
        )
        # Grant read access to our Kinesis stream
        self.event_trigger_role.add_to_policy(
            iam.PolicyStatement(
                actions=[
                    "kinesis:GetRecords",
                    "kinesis:GetShardIterator",
                    "kinesis:DescribeStream",
                    "kinesis:ListShards",
                    "kinesis:SubscribeToShard",
                ],
                resources=[self.ticket_stream.stream_arn],
            )
        )
        # Clean up role on stack removal
        self.event_trigger_role.apply_removal_policy(RemovalPolicy.DESTROY)

        # Create the Lambda function itself
        self.event_trigger_lambda = _lambda.Function(
            self,
            "ThesisTicketProcessorTriggerLambda",
            function_name="ThesisTicketProcessorTriggerLambda",
            runtime=_lambda.Runtime.PYTHON_3_11,
            handler="handler.lambda_handler",
            code=_lambda.Code.from_asset(
                "ticket_management_system/lambdas/TriggerSFN"
            ),
            timeout=Duration.seconds(30),
            role=self.event_trigger_role,
        )
        # Destroy on stack removal
        self.event_trigger_lambda.apply_removal_policy(RemovalPolicy.DESTROY)

        # Map the Kinesis stream to the Lambda with an event source mapping
        CfnEventSourceMapping(
            self,
            "FilteredKinesisMapping",
            function_name=self.event_trigger_lambda.function_name,
            event_source_arn=self.ticket_stream.stream_arn,
            starting_position="LATEST",
            batch_size=100,
            filter_criteria={"Filters": [{"Pattern": '{ \"eventName\": [\"TicketSubmitted\"] }'}]},
        ).apply_removal_policy(RemovalPolicy.DESTROY)

    def _create_response_generator_lambda(self) -> None:
        """
        Define a Lambda to call Bedrock (LLM) for response generation.

        - Builds a dependencies Layer (Python 3.11)
        - IAM role allows:
          • CloudWatch Logs (create, put events)
          • bedrock:InvokeModel
        - Timeout set to 60s
        """
        # Lambda Layer with shared dependencies for response generation
        self.response_generator_layer = _lambda.LayerVersion(
            self,
            "ThesisResponseGeneratorLayer",
            layer_version_name="ThesisResponseGeneratorLayer",
            code=_lambda.Code.from_asset(
                "ticket_management_system/lambda_layers/ResponseGenerator/lambda-layer.zip"
            ),
            compatible_runtimes=[_lambda.Runtime.PYTHON_3_11],
        )
        self.response_generator_layer.apply_removal_policy(RemovalPolicy.DESTROY)

        # IAM Role for the Lambda to write logs and invoke Bedrock
        self.response_generator_role = iam.Role(
            self,
            "ThesisResponseGeneratorRole",
            assumed_by=iam.ServicePrincipal("lambda.amazonaws.com"),
            role_name="ThesisResponseGeneratorRole"
        )
        # Logging permissions
        self.response_generator_role.add_to_policy(
            iam.PolicyStatement(
                actions=[
                    "logs:CreateLogGroup",
                    "logs:CreateLogStream",
                    "logs:PutLogEvents",
                ],
                resources=[f"arn:aws:logs:{self.region}:{self.account}:*"],
            )
        )

        self.response_generator_role.add_to_policy(
            iam.PolicyStatement(
                actions=["bedrock:InvokeModel"],
                resources=["*"],
            )
        )
        self.response_generator_role.apply_removal_policy(RemovalPolicy.DESTROY)

        self.response_generator_lambda = _lambda.Function(
            self,
            "ThesisResponseGeneratorLambda",
            function_name="ThesisResponseGeneratorLambda",
            runtime=_lambda.Runtime.PYTHON_3_11,
            handler="handler.lambda_handler",
            code=_lambda.Code.from_asset(
                "ticket_management_system/lambdas/ResponseGenerator"
            ),
            timeout=Duration.seconds(60),
            role=self.response_generator_role,
            layers=[self.response_generator_layer],
        )
        self.response_generator_lambda.apply_removal_policy(RemovalPolicy.DESTROY)

    def _create_s3_writer_lambda(self) -> None:
        """
        Create a Lambda that writes the LLM responses into S3.

        - IAM role with AWSLambdaBasicExecutionRole
        - Grants write access to the tickets S3 bucket
        - Reads environment variable S3_BUCKET_NAME
        - Timeout: 30s
        """
        # Role for S3 writer
        self.s3_writer_role = iam.Role(
            self,
            "ThesisS3WriterRole",
            assumed_by=iam.ServicePrincipal("lambda.amazonaws.com"),
            role_name="ThesisS3WriterRole"
        )
        # Basic execution role
        self.s3_writer_role.add_managed_policy(
            iam.ManagedPolicy.from_aws_managed_policy_name(
                "service-role/AWSLambdaBasicExecutionRole"
            )
        )
        # Grant write permissions to the bucket
        self.tickets_bucket.grant_write(self.s3_writer_role)
        self.s3_writer_role.apply_removal_policy(RemovalPolicy.DESTROY)

        # Create the Lambda
        self.s3_writer_lambda = _lambda.Function(
            self,
            "ThesisS3WriterLambda",
            function_name="ThesisS3WriterLambda",
            runtime=_lambda.Runtime.PYTHON_3_11,
            handler="handler.lambda_handler",
            code=_lambda.Code.from_asset(
                "ticket_management_system/lambdas/S3Writer"
            ),
            timeout=Duration.seconds(30),
            role=self.s3_writer_role,
            environment={
                "S3_BUCKET_NAME": self.tickets_bucket.bucket_name
            }
        )
        self.s3_writer_lambda.apply_removal_policy(RemovalPolicy.DESTROY)

    def _create_dynamodb_table(self) -> None:
        """
        Provision a DynamoDB table to track ticket metadata.

        Table configuration:
          • Name: ThesisTicketsTable
          • Partition key: ticket_id (String)
        """
        self.tickets_table = dynamodb.Table(
            self,
            "ThesisTicketsTable",
            table_name="ThesisTicketsTable",
            partition_key=dynamodb.Attribute(
                name="ticket_id", type=dynamodb.AttributeType.STRING
            ),
            removal_policy=RemovalPolicy.DESTROY,
        )

    def _create_s3_bucket(self) -> None:
        """
        Create an S3 bucket to store ticket data and generated outputs.

        - Bucket name: thesis-tickets-bucket
        - Auto-delete objects on removal
        - Grants write to the response-generator Lambda
        """
        self.tickets_bucket = s3.Bucket(
            self,
            "ThesisTicketsBucket",
            bucket_name="thesis-tickets-bucket",
            removal_policy=RemovalPolicy.DESTROY,
            auto_delete_objects=True,
        )
        # Allow response-generator to write into bucket
        self.tickets_bucket.grant_write(self.response_generator_role)

    def _create_sns_topic(self) -> None:
        """
        Set up an SNS topic for notification delivery and alarms.

        - Topic name & display: ThesisTicketNotificationsTopic
        - Subscribes the configured email address
        """
        self.notification_topic = sns.Topic(
            self,
            "ThesisTicketNotificationsTopic",
            topic_name="ThesisTicketNotificationsTopic",
            display_name="ThesisTicketNotificationsTopic",
        )

        self.notification_topic.apply_removal_policy(RemovalPolicy.DESTROY)
        for email in self.notification_emails:
            self.notification_topic.add_subscription(
                subs.EmailSubscription(email)
            )

    def _create_glue_job_and_schedule(self) -> None:
        """
        Configure an AWS Glue ETL job and schedule it via EventBridge.

        - Builds a JDBC Connection to Redshift using env vars
        - Glue job role with S3 read/write and Redshift credential permissions
        - Glue job runs Python 3 script from S3 (`scripts/ticket_processing_job.py`)
        - Default args include job-bookmarks, metrics, and temp dir
        - Runs every 2 hours via an EventBridge rule
        - Deploys local glue scripts to S3 on synth
        """
        # Create a JDBC connection for Redshift
        self.redshift_connection = glue.CfnConnection(
            self,
            "ThesisRedshiftConnection",
            catalog_id=self.account,
            connection_input=glue.CfnConnection.ConnectionInputProperty(
                name="thesis-redshift-connection",
                connection_type="JDBC",
                connection_properties={
                    "JDBC_CONNECTION_URL": self.redshift_jdbc_url,
                    "USERNAME": self.redshift_username,
                    "PASSWORD": self.redshift_password
                },
                physical_connection_requirements=glue.CfnConnection.PhysicalConnectionRequirementsProperty(
                    subnet_id=self.redshift_subnet_id,
                    security_group_id_list=[self.redshift_security_group_id],
                    availability_zone=self.availability_zone
                )
            )
        )

        # IAM Role for Glue job execution
        self.glue_job_role = iam.Role(
            self,
            "ThesisGlueJobRole",
            assumed_by=iam.ServicePrincipal("glue.amazonaws.com"),
            role_name="ThesisGlueJobRole"
        )
        self.glue_job_role.add_managed_policy(
            iam.ManagedPolicy.from_aws_managed_policy_name("service-role/AWSGlueServiceRole")
        )
        # Grant S3 read access
        self.tickets_bucket.grant_read(self.glue_job_role)
        # Grant Redshift credentials
        self.glue_job_role.add_to_policy(
            iam.PolicyStatement(
                actions=[
                    "redshift:GetClusterCredentials",
                    "redshift:CreateClusterUser",
                    "redshift:DescribeClusters"
                ],
                resources=[self.redshift_arn]
            )
        )
        # S3 permissions for temp dirs and scripts
        self.glue_job_role.add_to_policy(
            iam.PolicyStatement(
                actions=["s3:*"],
                resources=[
                    f"{self.tickets_bucket.bucket_arn}/temp/*",
                    f"{self.tickets_bucket.bucket_arn}/scripts/*"
                ]
            )
        )
        self.glue_job_role.apply_removal_policy(RemovalPolicy.DESTROY)

        # Define the Glue job
        self.glue_job = glue.CfnJob(
            self,
            "ThesisTicketProcessingJob",
            name="ThesisTicketProcessingJob",
            role=self.glue_job_role.role_arn,
            command=glue.CfnJob.JobCommandProperty(
                name="glueetl",
                python_version="3",
                script_location=f"s3://{self.tickets_bucket.bucket_name}/scripts/ticket_processing_job.py"
            ),
            connections=glue.CfnJob.ConnectionsListProperty(
                connections=[self.redshift_connection.connection_input.name]
            ),
            default_arguments={
                "--job-bookmark-option": "job-bookmark-enable",
                "--enable-metrics": "",
                "--enable-continuous-cloudwatch-log": "true",
                "--S3_BUCKET": self.tickets_bucket.bucket_name,
                "--REDSHIFT_DATABASE": self.redshift_database,
                "--REDSHIFT_SCHEMA": self.redshift_schema,
                "--REDSHIFT_TABLE": self.redshift_table,
                "--REDSHIFT_CONNECTION": self.redshift_connection.connection_input.name,
                "--TEMP_DIR": f"s3://{self.tickets_bucket.bucket_name}/temp/"
            },
            max_retries=0,
            timeout=600,
            glue_version="4.0",
            number_of_workers=2,
            worker_type="G.1X"
        )
        self.glue_job.apply_removal_policy(RemovalPolicy.DESTROY)

        # EventBridge rule to run the job every 2 hours
        self.glue_schedule_rule = events.Rule(
            self,
            "ThesisGlueJobSchedule",
            rule_name="ThesisGlueJobSchedule",
            schedule=events.Schedule.rate(Duration.hours(2)),
            description="Trigger Glue job to process new tickets every 2 hours"
        )
        # Add the Glue job as a target
        self.glue_schedule_rule.add_target(
            targets.AwsApi(
                service="glue",
                action="startJobRun",
                parameters={"JobName": self.glue_job.name},
                policy_statement=iam.PolicyStatement(
                    actions=["glue:StartJobRun"],
                    resources=[f"arn:aws:glue:{self.region}:{self.account}:job/{self.glue_job.name}"]
                )
            )
        )
        self.glue_schedule_rule.apply_removal_policy(RemovalPolicy.DESTROY)

        # Deploy local scripts to S3 for Glue
        s3deploy.BucketDeployment(
            self,
            "GlueScriptDeployment",
            sources=[s3deploy.Source.asset("ticket_management_system/glue_scripts")],
            destination_bucket=self.tickets_bucket,
            destination_key_prefix="scripts/"
        )

    def _create_step_function(self) -> None:
        """
        Define a Step Functions state machine for ticket workflow:

          1. Detect sentiment with Comprehend
          2. Invoke the response-generator Lambda
          3. Write metadata to DynamoDB and publish to SNS
          4. Save the response object to S3 via the writer Lambda

        - IAM role grants Comprehend, Lambda invoke, DynamoDB write, SNS publish
        - Loads ASL from `state_machine/state_machine.json` and substitutes ARNs/names
        - Deploys as a STANDARD state machine
        - Hooks the SFN ARN into the trigger Lambda’s environment
        """
        # IAM Role for State Machine execution
        self.state_machine_role = iam.Role(
            self,
            "StateMachineExecutionRole",
            assumed_by=iam.ServicePrincipal("states.amazonaws.com"),
            role_name="StateMachineExecutionRole"
        )
        self.state_machine_role.apply_removal_policy(RemovalPolicy.DESTROY)

        # Allow sentiment detection
        self.state_machine_role.add_to_policy(
            iam.PolicyStatement(
                actions=["comprehend:DetectSentiment"],
                resources=["*"]
            )
        )
        # Allow invoking the two Lambdas
        self.state_machine_role.add_to_policy(
            iam.PolicyStatement(
                actions=["lambda:InvokeFunction"],
                resources=[
                    self.response_generator_lambda.function_arn,
                    self.s3_writer_lambda.function_arn
                ]
            )
        )
        # Grant write to DynamoDB and publish to SNS
        self.tickets_table.grant_write_data(self.state_machine_role)
        self.notification_topic.grant_publish(self.state_machine_role)

        # Load the ASL definition from file and substitute ARNs/names
        state_machine_definition = pathlib.Path(__file__).parent.joinpath(
            "state_machine", "state_machine.json"
        ).read_text(encoding="utf-8")
        substitutions = {
            "ResponseGeneratorArn": self.response_generator_lambda.function_arn,
            "S3WriterArn": self.s3_writer_lambda.function_arn,
            "TicketsTableName": self.tickets_table.table_name,
            "NotificationTopicArn": self.notification_topic.topic_arn,
        }

        # Create the CloudFormation-based State Machine
        self.state_machine = sfn.CfnStateMachine(
            self,
            "TicketSentimentStateMachine",
            role_arn=self.state_machine_role.role_arn,
            state_machine_name="ThesisTicketStateMachine",
            state_machine_type="STANDARD",
            definition_string=state_machine_definition,
            definition_substitutions=substitutions,
        )
        self.state_machine.apply_removal_policy(RemovalPolicy.DESTROY)

        # Pass the SFN ARN to the event trigger Lambda environment
        self.event_trigger_lambda.add_environment("SFN_ARN", self.state_machine.attr_arn)
        # Allow Lambda to start the State Machine
        self.event_trigger_role.add_to_policy(
            iam.PolicyStatement(
                actions=["states:StartExecution"],
                resources=[self.state_machine.attr_arn]
            )
        )

    def _create_failure_alarm(self) -> None:
        """
        Create a CloudWatch alarm on Step Function failures and route
        notifications via the SNS topic.

        - Monitors AWS/States ExecutionsFailed metric for our state machine
        - Threshold: >0 failures over a 1‐minute period
        - Sends alerts to the existing SNS topic
        """
        # Build the metric for Step Function failures
        failure_metric = cloudwatch.Metric(
            namespace="AWS/States",
            metric_name="ExecutionsFailed",
            dimensions_map={
                "StateMachineArn": self.state_machine.attr_arn
            },
            statistic="Sum",
            period=Duration.minutes(1),
        )

        # Alarm if any failures occur
        self.failure_alarm = cloudwatch.Alarm(
            self,
            "ThesisStateMachineFailureAlarm",
            alarm_name="ThesisStateMachineFailureAlarm",
            metric=failure_metric,
            evaluation_periods=1,
            threshold=0,
            comparison_operator=cloudwatch.ComparisonOperator.GREATER_THAN_THRESHOLD,
            treat_missing_data=cloudwatch.TreatMissingData.MISSING,
        )

        # Use the same SNS topic
        self.failure_alarm.add_alarm_action(
            cw_actions.SnsAction(self.notification_topic)
        )

