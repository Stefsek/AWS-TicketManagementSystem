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
    AWS CDK Stack for Stefanos Sekis' thesis project.

    Provisions a complete AWS-based ticket management system with:
      1. Kinesis Data Stream → ticket ingestion
      2. Lambda functions → event triggering, response generation, S3 writing
      3. DynamoDB table → ticket metadata
      4. S3 bucket → ticket data and generated responses
      5. SNS topic → notifications and alarms
      6. AWS Glue job + EventBridge → ETL into Redshift
      7. Step Functions state machine → orchestration of ticket workflow
      8. CloudWatch alarm → failure monitoring

    Notes:
    - Environment variables (Redshift connectivity, VPC networking, emails, etc.)
      are read from `.env`.
    - All resources use `RemovalPolicy.DESTROY` for easy cleanup in dev/thesis envs.
    """

    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        """
        Initialize the CDK stack and sequentially provision all resources.
        """
        super().__init__(scope, construct_id, **kwargs)

        # Load configuration and provision resources in dependency order
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
        Load required environment variables from `.env` and assign them
        to instance attributes. Ensures Redshift + networking config is present.

        Raises:
            ValueError: if any required environment variable is missing.
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

        # Assign Redshift + networking config
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

        # Parse notification emails and project name
        emails = os.getenv("NOTIFICATION_EMAILS", "")
        self.notification_emails = [e.strip() for e in emails.split(",") if e.strip()]
        self.project_name = os.getenv("PROJECT_NAME")

    def _create_kinesis_stream(self) -> None:
        """
        Create a Kinesis Data Stream for ingesting raw ticket events.
        """
        self.ticket_stream = kinesis.Stream(
            self,
            f"{self.project_name}KinesisStream",
            stream_name=f"{self.project_name}-kinesis-stream",
            shard_count=1,  # single shard is enough for demo
            retention_period=Duration.hours(24),
        )
        self.ticket_stream.apply_removal_policy(RemovalPolicy.DESTROY)

    def _create_event_trigger_lambda(self) -> None:
        """
        Lambda that consumes Kinesis events and triggers the Step Functions workflow.
        Filters only events with `eventName: TicketSubmitted`.
        """
        # IAM role with Kinesis read + StepFunctions start permissions
        self.event_trigger_role = iam.Role(
            self,
            f"{self.project_name}SfnTriggerRole",
            assumed_by=iam.ServicePrincipal("lambda.amazonaws.com"),
            role_name=f"{self.project_name}-sfn-trigger-role"
        )
        self.event_trigger_role.add_managed_policy(
            iam.ManagedPolicy.from_aws_managed_policy_name(
                "service-role/AWSLambdaBasicExecutionRole"
            )
        )
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
        self.event_trigger_role.apply_removal_policy(RemovalPolicy.DESTROY)

        # Lambda definition
        self.event_trigger_lambda = _lambda.Function(
            self,
            f"{self.project_name}SfnTrigger",
            function_name=f"{self.project_name}-sfn-trigger",
            runtime=_lambda.Runtime.PYTHON_3_11,
            handler="handler.lambda_handler",
            code=_lambda.Code.from_asset("ticket_management_system/lambdas/TriggerSFN"),
            timeout=Duration.seconds(30),
            role=self.event_trigger_role,
        )
        self.event_trigger_lambda.apply_removal_policy(RemovalPolicy.DESTROY)

        # Event source mapping with JSON filter
        CfnEventSourceMapping(
            self,
            "FilteredKinesisMapping",
            function_name=self.event_trigger_lambda.function_name,
            event_source_arn=self.ticket_stream.stream_arn,
            starting_position="LATEST",
            batch_size=100,
            filter_criteria={"Filters": [{"Pattern": '{ "eventName": ["TicketSubmitted"] }'}]},
        ).apply_removal_policy(RemovalPolicy.DESTROY)

    def _create_response_generator_lambda(self) -> None:
        """
        Lambda that calls AWS Bedrock (LLM) to generate automated responses.
        """
        # Dependency layer
        self.response_generator_layer = _lambda.LayerVersion(
            self,
            f"{self.project_name}ResponseGeneratorLayer",
            layer_version_name=f"{self.project_name}-response-generator-layer",
            code=_lambda.Code.from_asset(
                "ticket_management_system/lambda_layers/ResponseGenerator/lambda-layer.zip"
            ),
            compatible_runtimes=[_lambda.Runtime.PYTHON_3_11],
        )
        self.response_generator_layer.apply_removal_policy(RemovalPolicy.DESTROY)

        # IAM role with logging + bedrock:InvokeModel
        self.response_generator_role = iam.Role(
            self,
            f"{self.project_name}ResponseGeneratorRole",
            assumed_by=iam.ServicePrincipal("lambda.amazonaws.com"),
            role_name=f"{self.project_name}ResponseGeneratorRole"
        )
        self.response_generator_role.add_to_policy(
            iam.PolicyStatement(
                actions=["logs:CreateLogGroup", "logs:CreateLogStream", "logs:PutLogEvents"],
                resources=[f"arn:aws:logs:{self.region}:{self.account}:*"],
            )
        )
        self.response_generator_role.add_to_policy(
            iam.PolicyStatement(actions=["bedrock:InvokeModel"], resources=["*"])
        )
        self.response_generator_role.apply_removal_policy(RemovalPolicy.DESTROY)

        # Lambda definition
        self.response_generator_lambda = _lambda.Function(
            self,
            f"{self.project_name}ResponseGenerator",
            function_name=f"{self.project_name}-response-generator",
            runtime=_lambda.Runtime.PYTHON_3_11,
            handler="handler.lambda_handler",
            code=_lambda.Code.from_asset("ticket_management_system/lambdas/ResponseGenerator"),
            timeout=Duration.seconds(60),
            role=self.response_generator_role,
            layers=[self.response_generator_layer],
        )
        self.response_generator_lambda.apply_removal_policy(RemovalPolicy.DESTROY)

    def _create_s3_writer_lambda(self) -> None:
        """
        Lambda that writes processed tickets (LLM + metadata) into S3.
        """
        # IAM role with basic execution + bucket write access
        self.s3_writer_role = iam.Role(
            self,
            f"{self.project_name}S3WriterRole",
            assumed_by=iam.ServicePrincipal("lambda.amazonaws.com"),
            role_name=f"{self.project_name}-s3-writer-role"
        )
        self.s3_writer_role.add_managed_policy(
            iam.ManagedPolicy.from_aws_managed_policy_name("service-role/AWSLambdaBasicExecutionRole")
        )
        self.tickets_bucket.grant_write(self.s3_writer_role)
        self.s3_writer_role.apply_removal_policy(RemovalPolicy.DESTROY)

        # Lambda definition
        self.s3_writer_lambda = _lambda.Function(
            self,
            f"{self.project_name}S3Writer",
            function_name=f"{self.project_name}-s3-writer",
            runtime=_lambda.Runtime.PYTHON_3_11,
            handler="handler.lambda_handler",
            code=_lambda.Code.from_asset("ticket_management_system/lambdas/S3Writer"),
            timeout=Duration.seconds(30),
            role=self.s3_writer_role,
            environment={"S3_BUCKET_NAME": self.tickets_bucket.bucket_name},
        )
        self.s3_writer_lambda.apply_removal_policy(RemovalPolicy.DESTROY)

    def _create_dynamodb_table(self) -> None:
        """
        DynamoDB table to store ticket metadata (ID, timestamps, status).
        """
        self.tickets_table = dynamodb.Table(
            self,
            f"{self.project_name}DdbTable",
            table_name=f"{self.project_name}-ddb-table",
            partition_key=dynamodb.Attribute(name="ticket_id", type=dynamodb.AttributeType.STRING),
            removal_policy=RemovalPolicy.DESTROY,
        )

    def _create_s3_bucket(self) -> None:
        """
        S3 bucket to store full processed ticket JSONs.
        """
        self.tickets_bucket = s3.Bucket(
            self,
            f"{self.project_name}Bucket",
            bucket_name=f"{self.project_name}-bucket".lower(),
            removal_policy=RemovalPolicy.DESTROY,
            auto_delete_objects=True,
        )
        self.tickets_bucket.grant_write(self.response_generator_role)

    def _create_sns_topic(self) -> None:
        """
        SNS topic for notifications and alerts (subscribed emails).
        """
        self.notification_topic = sns.Topic(
            self,
            f"{self.project_name}NotificationsTopic",
            topic_name=f"{self.project_name}NotificationsTopic",
            display_name=f"{self.project_name}NotificationsTopic",
        )
        self.notification_topic.apply_removal_policy(RemovalPolicy.DESTROY)

        # Subscribe configured emails
        for email in self.notification_emails:
            self.notification_topic.add_subscription(subs.EmailSubscription(email))

    def _create_glue_job_and_schedule(self) -> None:
        """
        AWS Glue ETL job to load ticket JSONs from S3 into Redshift.
        Scheduled via EventBridge every 2 hours.
        """
        # Redshift JDBC connection
        self.redshift_connection = glue.CfnConnection(
            self,
            f"{self.project_name}RedshiftConnection",
            catalog_id=self.account,
            connection_input=glue.CfnConnection.ConnectionInputProperty(
                name=f"{self.project_name}-redshift-connection",
                connection_type="JDBC",
                connection_properties={
                    "JDBC_CONNECTION_URL": self.redshift_jdbc_url,
                    "USERNAME": self.redshift_username,
                    "PASSWORD": self.redshift_password,
                },
                physical_connection_requirements=glue.CfnConnection.PhysicalConnectionRequirementsProperty(
                    subnet_id=self.redshift_subnet_id,
                    security_group_id_list=[self.redshift_security_group_id],
                    availability_zone=self.availability_zone,
                ),
            ),
        )

        # IAM role for Glue job (S3 + Redshift access)
        self.glue_job_role = iam.Role(
            self,
            f"{self.project_name}GlueJobRole",
            assumed_by=iam.ServicePrincipal("glue.amazonaws.com"),
            role_name=f"{self.project_name}-glue-job-role"
        )
        self.glue_job_role.add_managed_policy(
            iam.ManagedPolicy.from_aws_managed_policy_name("service-role/AWSGlueServiceRole")
        )
        self.tickets_bucket.grant_read(self.glue_job_role)
        self.glue_job_role.add_to_policy(
            iam.PolicyStatement(
                actions=["redshift:GetClusterCredentials", "redshift:CreateClusterUser", "redshift:DescribeClusters"],
                resources=[self.redshift_arn],
            )
        )
        self.glue_job_role.apply_removal_policy(RemovalPolicy.DESTROY)

        # Glue job definition
        self.glue_job = glue.CfnJob(
            self,
            f"{self.project_name}Job",
            name=f"{self.project_name}-job",
            role=self.glue_job_role.role_arn,
            command=glue.CfnJob.JobCommandProperty(
                name="glueetl",
                python_version="3",
                script_location=f"s3://{self.tickets_bucket.bucket_name}/scripts/ticket_processing_job.py",
            ),
            connections=glue.CfnJob.ConnectionsListProperty(
                connections=[self.redshift_connection.connection_input.name]
            ),
            default_arguments={
                "--S3_BUCKET": self.tickets_bucket.bucket_name,
                "--REDSHIFT_DATABASE": self.redshift_database,
                "--REDSHIFT_SCHEMA": self.redshift_schema,
                "--REDSHIFT_TABLE": self.redshift_table,
                "--REDSHIFT_CONNECTION": self.redshift_connection.connection_input.name,
                "--TEMP_DIR": f"s3://{self.tickets_bucket.bucket_name}/temp/",
                "--job-bookmark-option": "job-bookmark-enable",
                "--enable-metrics": "",
                "--enable-continuous-cloudwatch-log": "true",
            },
            timeout=600,
            glue_version="4.0",
            number_of_workers=2,
            worker_type="G.1X",
        )
        self.glue_job.apply_removal_policy(RemovalPolicy.DESTROY)

        # EventBridge rule to run job every 2h
        self.glue_schedule_rule = events.Rule(
            self,
            f"{self.project_name}JobSchedule",
            rule_name=f"{self.project_name}-job-schedule",
            schedule=events.Schedule.rate(Duration.hours(2)),
            description="Trigger Glue job every 2 hours",
        )
        self.glue_schedule_rule.add_target(
            targets.AwsApi(
                service="glue",
                action="startJobRun",
                parameters={"JobName": self.glue_job.name},
                policy_statement=iam.PolicyStatement(
                    actions=["glue:StartJobRun"],
                    resources=[f"arn:aws:glue:{self.region}:{self.account}:job/{self.glue_job.name}"],
                ),
            )
        )
        self.glue_schedule_rule.apply_removal_policy(RemovalPolicy.DESTROY)

        # Deploy local Glue scripts to S3
        s3deploy.BucketDeployment(
            self,
            "GlueScriptDeployment",
            sources=[s3deploy.Source.asset("ticket_management_system/glue_scripts")],
            destination_bucket=self.tickets_bucket,
            destination_key_prefix="scripts/",
        )

    def _create_step_function(self) -> None:
        """
        Step Functions workflow for ticket processing:
          1. Detect sentiment (Comprehend)
          2. Generate response (Bedrock Lambda)
          3. Write metadata (DynamoDB + SNS)
          4. Write full object (S3 Writer Lambda)
        """
        self.state_machine_role = iam.Role(
            self,
            f"{self.project_name}SfnRole",
            assumed_by=iam.ServicePrincipal("states.amazonaws.com"),
            role_name=f"{self.project_name}-sfn-role"
        )
        self.state_machine_role.apply_removal_policy(RemovalPolicy.DESTROY)

        # Grant required permissions
        self.state_machine_role.add_to_policy(iam.PolicyStatement(actions=["comprehend:DetectSentiment"], resources=["*"]))
        self.state_machine_role.add_to_policy(iam.PolicyStatement(actions=["lambda:InvokeFunction"], resources=[
            self.response_generator_lambda.function_arn, self.s3_writer_lambda.function_arn
        ]))
        self.tickets_table.grant_write_data(self.state_machine_role)
        self.notification_topic.grant_publish(self.state_machine_role)

        # Load ASL definition and substitute ARNs
        state_machine_definition = pathlib.Path(__file__).parent.joinpath("state_machine", "state_machine.json").read_text()
        substitutions = {
            "ResponseGeneratorArn": self.response_generator_lambda.function_arn,
            "S3WriterArn": self.s3_writer_lambda.function_arn,
            "TicketsTableName": self.tickets_table.table_name,
            "NotificationTopicArn": self.notification_topic.topic_arn,
        }

        self.state_machine = sfn.CfnStateMachine(
            self,
            f"{self.project_name}Sfn",
            role_arn=self.state_machine_role.role_arn,
            state_machine_name=f"{self.project_name}-sfn",
            state_machine_type="STANDARD",
            definition_string=state_machine_definition,
            definition_substitutions=substitutions,
        )
        self.state_machine.apply_removal_policy(RemovalPolicy.DESTROY)

        # Pass ARN into trigger Lambda env
        self.event_trigger_lambda.add_environment("SFN_ARN", self.state_machine.attr_arn)
        self.event_trigger_role.add_to_policy(
            iam.PolicyStatement(actions=["states:StartExecution"], resources=[self.state_machine.attr_arn])
        )

    def _create_failure_alarm(self) -> None:
        """
        CloudWatch alarm → triggers SNS notification if Step Functions execution fails.
        """
        failure_metric = cloudwatch.Metric(
            namespace="AWS/States",
            metric_name="ExecutionsFailed",
            dimensions_map={"StateMachineArn": self.state_machine.attr_arn},
            statistic="Sum",
            period=Duration.minutes(1),
        )
        self.failure_alarm = cloudwatch.Alarm(
            self,
            f"{self.project_name}SfnFailureAlarm",
            alarm_name=f"{self.project_name}-sfn-failure-alarm",
            metric=failure_metric,
            evaluation_periods=1,
            threshold=0,
            comparison_operator=cloudwatch.ComparisonOperator.GREATER_THAN_THRESHOLD,
            treat_missing_data=cloudwatch.TreatMissingData.MISSING,
        )
        self.failure_alarm.add_alarm_action(cw_actions.SnsAction(self.notification_topic))


