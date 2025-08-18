# AWS Ticket Management System (Thesis Project)

**Repository:** [Stefsek/AWS-TicketManagementSystem](https://github.com/Stefsek/AWS-TicketManagementSystem)

---

## Introduction

This project provides an end-to-end **ticket management system** built with the AWS Cloud Development Kit (CDK) in Python. It is designed to:

1. **Ingest** incoming support tickets via **Kinesis Data Stream**
2. **Orchestrate** processing with **Step Functions**
3. **Analyze sentiment** using Amazon Comprehend
4. **Generate first response ai messages** via Bedrock LLM (in a Lambda)
5. **Persist** metadata in **DynamoDB** and full JSON in **S3**
6. **Notify** Notifications with **SNS**
7. **ETL** all data into **Amazon Redshift** via an **AWS Glue** job
8. **Monitor** failures with **CloudWatch Alarms**

Every resource is defined in the CDK stack (`ticket_management_system/stack.py`) and uses `RemovalPolicy.DESTROY` for convenient teardown in a development or thesis environment. Configuration (Redshift JDBC URL, credentials, networking) is read from a local `.env` file.

---

## Architecture Overview

Below is a simplified flow of how a ticket travels through the system:

```text
[TicketGenerator/main.py]
            |
            v
+------------------------------+
|    Kinesis Data Stream      |
+------------------------------+
            |
            v
+------------------------------+
|   TriggerSFN Lambda         |
+------------------------------+
            |
            v
+------------------------------+
| Step Functions State Machine|
+------------------------------+
       /       |        \
      v        v         v
+-----------+ +------------+ +-------------+
|Comprehend| |ResponseGen | | S3Writer    |
| Detect    | | Lambda     | | Lambda      |
+-----------+ +------------+ +-------------+
      |           |              |
      v           v              v
+-----------+ +------------+ +-------------+
| SNS Topic | | DynamoDB    | | S3 Bucket   |
+-----------+ +------------+ +-------------+
      |           |              |
      v           v              v
[Email Subs]  (metadata)   (JSON files)
      |
      v
+------------------------------+
| High Priority Alert → SNS    |
+------------------------------+
      |
      v
+------------------------------+
|   Glue ETL Job → Redshift    |
+------------------------------+
      |
      v
+------------------------------+
|  CloudWatch Alarm on Fail    |
+------------------------------+
```

Each numbered step below corresponds to a CDK method in `stack.py`.

---

## AWS Services & Components

### 1. Kinesis Data Stream (`_create_kinesis_stream`)

- **Purpose:** Ingest raw ticket events with high throughput and durability.
- **Config:** Single shard, 24‑hour retention, auto-destroy on stack deletion.

### 2. Lambda: **TriggerSFN** (`_create_event_trigger_lambda`)

- **Code:** `ticket_management_system/lambdas/TriggerSFN/handler.py`
- **Role Permissions:** Read from Kinesis & Start Step Functions execution.
- **Behavior:** Filters records for `eventName: TicketSubmitted` and starts state machine with the ticket payload.

### 3. Step Functions State Machine (`_create_step_function`)

- **Definition:** JSON in `ticket_management_system/state_machine/state_machine.json`
- **Steps:**
  1. **DetectSentiment** (Comprehend)
  2. **ResponseGenerator** Lambda
  3. **WriteMetadata** (DynamoDB + SNS)
  4. **S3Writer** Lambda
- **High-Priority Alerts:** f the generated priority is HIGH, the workflow immediately publishes an alert to the SNS topic before continuing the normal flow.
- **Role:** Permissions for Comprehend, Lambda Invoke, DynamoDB write, SNS publish.

### 4. Lambda: **ResponseGenerator** (`_create_response_generator_lambda`)

- **Layer:** Shared dependencies at `ticket_management_system/lambda_layers/ResponseGenerator`.
- **Code:** `ticket_management_system/lambdas/ResponseGenerator/handler.py`
- **Role Permissions:** CloudWatch Logs & `bedrock:InvokeModel`.
- **Function:** Formats prompt, calls Bedrock LLM, returns customer response, priority, reasoning.

### 5. DynamoDB Table (`_create_dynamodb_table`)

- **Name:** `ThesisTicketsTable`
- **Partition Key:** `ticket_id` (String)
- **Tracks:** Ticket metadata (ID, status, timestamps).

### 6. SNS Topic (`_create_sns_topic`)

- **Name:** `ThesisTicketNotificationsTopic`
- **Subscription:** Email (configured address) for immediate notifications.

### 7. Lambda: **S3Writer** (`_create_s3_writer_lambda`)

- **Code:** `ticket_management_system/lambdas/S3Writer/handler.py`
- **Role Permissions:** Write to S3 bucket.
- **Behavior:** Receives full ticket + LLM + sentiment output, transforms to flat JSON, stores under `tickets/YYYY/MM/DD/ticket_<ID>.json`.

### 8. Lambda: **TriggerSFN** (`_create_event_trigger_lambda`)

- **Code:** `ticket_management_system/lambdas/TriggerSFN/handler.py`
- **Role Permissions:** Triggers the state machine.
- **Behavior:** Starts by receiving a ticket with specific event name and triggers the state machine. 

### 9. S3 Bucket (`_create_s3_bucket`)

- **Name:** `thesis-tickets-bucket`
- **Config:** Auto-delete objects on stack destroy.
- **Purpose:** Long‑term storage of processed ticket JSON.

### 10. AWS Glue Job & Schedule (`_create_glue_job_and_schedule`)

- **Glue Connection:** JDBC → Redshift using `.env` variables.
- **Glue Script:** `ticket_management_system/glue_scripts/ticket_processing_job.py`
  - Extract: Read JSON from S3
  - Transform: Cast schema & validate no nulls
  - Load: COPY into Redshift
- **Schedule:** EventBridge rule triggers every 2 hours.
- **IAM:** S3 read/write, Redshift credentials, Glue service role.

### 11. CloudWatch Alarm (`_create_failure_alarm`)

- **Metric:** `AWS/States.ExecutionsFailed` for the state machine.
- **Threshold:** >0 failures in 1 minute.
- **Action:** Publish to SNS topic.

---

## Scripts

### `TicketGenerator/main.py`

- **Purpose:** Generate realistic dummy tickets with LangChain + Bedrock, then push to Kinesis.  
  - ⚠️ Requires **AWS Bedrock access** with permissions to invoke Nova models.  
  - If Bedrock is unavailable, you can substitute another LLM provider (e.g., OpenAI GPT) — update the code accordingly and supply the necessary API key.  
- **Key Steps:**
  1. Use `issue_scenarios` dictionary to pick a product and issue type.
  2. Use `TicketGeneratorOutputParser` to format JSON ticket.
  3. Send `put_record` to `thesis-ticket-stream` with payload:
     ```json
     { "eventName": "TicketSubmitted", "ticketId": "TKT-...", "submittedAt": "ISO...", "data": {...} }
     ```

### `TicketResponseEvaluator/main.py`

- **Purpose:** Evaluate the quality of LLM-generated ticket responses against strict AWS Support standards.  
  - ⚠️ Requires **AWS Bedrock access** with permissions to invoke Nova models.  
  - If Bedrock is unavailable, you can substitute another LLM provider (e.g., OpenAI GPT) — update the code accordingly and supply the necessary API key.  
- **Inputs:** Processed tickets stored in `ProcessedTickets/processed_tickets000.json`.  

- **Evaluation Criteria (booleans only):**
  1. **contextual_relevance** – Response explicitly acknowledges the AWS service/problem in the ticket.  
  2. **technical_accuracy** – All AWS details are factually correct, safe, and applicable.  
  3. **professional_tone** – Tone is formal, polite, and consistent with AWS support standards.  
  4. **actionable_guidance** – Response provides 2–3 specific, executable troubleshooting steps.  

- **Workflow:**
  1. Load processed tickets (JSON lines).  
  2. Build strict evaluation prompt (`Prompts/ticket_response_evaluator_prompts.py`).  
  3. Run evaluation with **AWS Bedrock** (`us.amazon.nova-pro-v1:0`).  
  4. Parse output using schema in `Schemas/ticket_response_evaluator_output_parser.py`.  
  5. Save evaluations to `ticket_evaluations.pkl`.  

- **Example Output:**
  ```json
  {
    "output": {
      "contextual_relevance": true,
      "technical_accuracy": true,
      "professional_tone": true,
      "actionable_guidance": false
    }
  }

### CDK Entry (`app.py` / `cdk.json`)

- \`\`**:** Bootstraps the stack in your AWS account/region.
- \`\`**:** Configuration for CDK commands.

---

## Prerequisites & Setup

Before deploying this stack, make sure the following AWS resources **already exist** in your account/region:

1. **Amazon Redshift Cluster**

   - A provisioned Redshift cluster to host your data warehouse.
   - Note its **JDBC endpoint** (for `REDSHIFT_JDBC_CONNECTION_URL`) and cluster **ARN** (`REDSHIFT_ARN`).

2. **Database, Schema & Table** in Redshift

   - Create the target database (e.g. `data`).
   - Create or grant privileges on the schema (e.g. `demo_workspace`).
   - Create the empty table (e.g. `processed_tickets`) with columns matching the Glue schema. A SQL script is provided in the `sql` folder (`sql/create_processed_tickets.sql`) containing:
     ```sql
     CREATE TABLE IF NOT EXISTS ${REDSHIFT_SCHEMA}.${REDSHIFT_TABLE} (
         ticket_id character varying(50) NOT NULL ENCODE lzo,
         submitted_at timestamp without time zone NOT NULL ENCODE az64,
         customer_first_name character varying(50) ENCODE lzo,
         customer_last_name character varying(50) ENCODE lzo,
         customer_full_name character varying(50) ENCODE lzo,
         customer_email character varying(50) ENCODE lzo,
         product character varying(50) ENCODE lzo,
         issue_type character varying(50) ENCODE lzo,
         subject character varying(500) ENCODE lzo,
         description character varying(5000) ENCODE lzo,
         response_text character varying(5000) ENCODE lzo,
         sentiment character varying(20) ENCODE lzo,
         sentiment_score_mixed double precision ENCODE raw,
         sentiment_score_negative double precision ENCODE raw,
         sentiment_score_neutral double precision ENCODE raw,
         sentiment_score_positive double precision ENCODE raw,
         priority character varying(20) ENCODE lzo,
         priority_reasoning character varying(5000) ENCODE lzo,
         processed_at timestamp without time zone ENCODE az64,
         PRIMARY KEY (ticket_id)
     )
     DISTSTYLE AUTO;
     ```

3. **VPC Networking**

   - At least one **subnet** (ID for `REDSHIFT_SUBNET_ID`) in the cluster’s VPC.
   - A **security group** (ID for `REDSHIFT_SECURITY_GROUP_ID`) allowing inbound JDBC traffic.
   - Ensure your subnet’s AZ matches `AVAILABILITY_ZONE` used by the cluster.

4. **IAM Permissions**

   - Your AWS user or role must be able to:
     - Create and manage all CDK resources (Lambda, Kinesis, Glue, etc.).
     - Read/write to the existing Redshift cluster via Glue’s IAM role.

5. **Email Addresses** for Notifications

   - Any valid email(s) that should receive SNS alerts on workflow failures.

6. **AWS Bedrock Access**
   - Ensure your AWS principal has permissions to invoke AWS Bedrock LLM models (e.g., `nova-pro-v1`) and that Bedrock is enabled in your account.

7. **AWS CLI** with proper IAM rights

   - Install the AWS CLI (v2) and configure it using `aws configure` or environment variables.  
   - You must create an **AWS CLI named profile** with your **Access Key ID** and **Secret Access Key**, ensuring it has sufficient IAM permissions to deploy and manage the resources in this project.  
   - For detailed setup, follow the AWS CLI Quickstart Guide: https://docs.aws.amazon.com/cli/latest/userguide/getting-started-quickstart.html

8. **Node.js (v16+) & AWS CDK v2**

   - Install Node.js version 16 or higher.
   - Install the AWS CDK v2 globally (`npm install -g aws-cdk`).
   - This provides the `cdk` command for synthesizing and deploying the infrastructure.

9. **Python 3.11 & Virtual Environment**

   - Ensure Python 3.11 is installed on your system.
   - Create and activate a virtual environment (`python3.11 -m venv .venv` & `source .venv/bin/activate`).
   - Install Python dependencies with `pip install -r requirements.txt`.

10. **Docker (optional, for local Lambda testing)**

   - If you want to test Lambdas locally (`cdk synth`, `cdk deploy --watch`), install Docker.
   - CDK can use Docker to build and emulate Lambda runtimes, ensuring compatibility with AWS.

Once these prerequisites are in place, continue with the setup steps below.

**Environment Variables (**\.env\**):**

````bash
# Unique project/resource name prefix used throughout the CDK stack
PROJECT_NAME=<YOUR_PROJECT_NAME>

# Redshift connection URL (JDBC)
REDSHIFT_JDBC_CONNECTION_URL=<YOUR_REDSHIFT_JDBC_URL>

# Redshift cluster ARN for Glue authentication
REDSHIFT_ARN=<YOUR_REDSHIFT_CLUSTER_ARN>

# Credentials to log in to Redshift
REDSHIFT_USERNAME=<YOUR_REDSHIFT_USERNAME>
REDSHIFT_PASSWORD=<YOUR_REDSHIFT_PASSWORD>

# Target database, schema, and table names in Redshift
REDSHIFT_DATABASE=<REDSHIFT_DATABASE_NAME>
REDSHIFT_SCHEMA=<REDSHIFT_SCHEMA_NAME>
REDSHIFT_TABLE=<REDSHIFT_TABLE_NAME>

# Networking details for Redshift VPC connectivity
REDSHIFT_SUBNET_ID=<YOUR_SUBNET_ID>
REDSHIFT_SECURITY_GROUP_ID=<YOUR_SECURITY_GROUP_ID>
AVAILABILITY_ZONE=<YOUR_AWS_AZ>

# Comma-separated list of notification email addresses for SNS alerts
NOTIFICATION_EMAILS=<EMAIL_ADDRESS_1>,<EMAIL_ADDRESS_2>

# AWS region where resources will be deployed
AWS_REGION=<YOUR_AWS_REGION>
````

Each variable explained:

- **REDSHIFT\_JDBC\_CONNECTION\_URL**: JDBC endpoint used by Glue to connect and load data into Redshift.

- **REDSHIFT\_ARN**: Amazon Resource Name for your Redshift cluster; needed for Glue to retrieve temporary credentials.

- **REDSHIFT\_USERNAME / REDSHIFT\_PASSWORD**: Authentication details for Redshift; Glue and CDK use these when establishing the connection.

- **REDSHIFT\_DATABASE / SCHEMA / TABLE**: Specify where processed tickets should be loaded in Redshift to organize data.

- **REDSHIFT\_SUBNET\_ID / REDSHIFT\_SECURITY\_GROUP\_ID / AVAILABILITY\_ZONE**: Network settings ensuring Glue jobs can reach Redshift inside a VPC.

- **NOTIFICATION\_EMAILS**: Defines who will receive SNS notifications on Step Function failures or other alerts.

- **AWS\_REGION**: Tells CDK and Lambdas which AWS region to provision and target services in.

- **PROJECT\NAME**: Unique project/resource name prefix used by the CDK stack to consistently name all AWS resources (streams, functions, tables, buckets, etc.).

> **Important:** Never commit real credentials or ARNs to Git. Use the placeholders above in your local `.env`, and add `.env` to your `.gitignore` to keep them safe. git clone ... cd AWS-TicketManagementSystem python3 -m venv .venv && source .venv/bin/activate pip install -r requirements.txt npm install -g aws-cdk cdk bootstrap aws\:/// cdk deploy


## Deploy

```bash
cdk deploy
````

---

## Testing & Validation

1. **Generate tickets:** `TicketGenerator/main.py`
2. **Monitor:** Kinesis, State Machine,Lambda logs in CloudWatch
3. **Verify:** DynamoDB table entries & S3 JSON files
4. **Check ETL:** Glue job runs and data appears in Redshift
5. **Alarm:** Force a Step Function error to test SNS email,get notifications for HIGH priority labelled tickets

---

## Cleanup

```bash
cdk destroy
````

All AWS resources will be removed, including data in DynamoDB, S3, Glue, etc.

