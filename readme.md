# AWS Ticket Management System (Thesis Project)

**Repository:** [Stefsek/AWS-TicketManagementSystem](https://github.com/Stefsek/AWS-TicketManagementSystem)

---

## 📘 Introduction
This project provides an end-to-end **ticket management system** built with the AWS Cloud Development Kit (CDK) in Python. It is designed to:

1. **Ingest** incoming support tickets via **Kinesis Data Stream**
2. **Orchestrate** processing with **Step Functions**
3. **Analyze sentiment** using Amazon Comprehend
4. **Generate automated responses** via Bedrock LLM (in a Lambda)
5. **Persist** metadata in **DynamoDB** and full JSON in **S3**
6. **Notify** stakeholders with **SNS**
7. **ETL** all data into **Amazon Redshift** via an **AWS Glue** job
8. **Monitor** failures with **CloudWatch Alarms**

Every resource is defined in the CDK stack (`ticket_management_system/stack.py`) and uses `RemovalPolicy.DESTROY` for convenient teardown in a development or thesis environment. Configuration (Redshift JDBC URL, credentials, networking) is read from a local `.env` file.

---

## 🏛 Architecture Overview
Below is a simplified flow of how a ticket travels through the system:

```text
[Ticket Generator Script]       ┌──────────────────┐
        │                        │ Kinesis Data      │
        ▼                        │ Stream (1 shard)  │
┌────────────────┐               └──────────────────┘
│ scripts/       │                       │
│ generate_      │                       ▼
│ ticket.py      │             ┌──────────────────────────┐
└────────────────┘             │ TriggerSFN Lambda (Event  │
        │                      │ filter + Start StepFn)    │
        ▼                      └──────────────────────────┘
                              │       ▲
                              │       │
                              ▼       │
                    ┌──────────────────────────┐         ┌──────────┐
                    │ AWS Step Functions       │ ───────▶│ Comprehend│
                    │ (State Machine)          │         │ Detect   │
                    │ 1. DetectSentiment       │         │ Sentiment│
                    │ 2. Invoke LLM Lambda     │         └──────────┘
                    │ 3. Write Metadata        │              │
                    │    to DynamoDB           │              ▼
                    │ 4. Publish SNS           │         ┌──────────┐
                    │ 5. Invoke S3Writer       │         │ S3 Bucket│
                    └──────────────────────────┘         │ (JSON)   │
                              │                          └──────────┘
                              ▼                              │
                        ┌──────────┐                         ▼
                        │ SNS      │                   ┌────────────┐
                        │ Topic    │                   │ Glue ETL   │
                        │ (Email)  │                   │ Job →      │
                        └──────────┘                   │ Redshift   │
                              │                        └────────────┘
                              ▼                              │
                        [Subscriber]                       ▼
                                              ┌────────────────────────┐
                                              │ CloudWatch Alarm on    │
                                              │ Step Function failure  │
                                              └────────────────────────┘
```  

Each numbered step below corresponds to a CDK method in `stack.py`.

---

## 🛠️ AWS Services & Components

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

### 8. S3 Bucket (`_create_s3_bucket`)
- **Name:** `thesis-tickets-bucket`
- **Config:** Auto-delete objects on stack destroy.
- **Purpose:** Long‑term storage of processed ticket JSON.

### 9. AWS Glue Job & Schedule (`_create_glue_job_and_schedule`)
- **Glue Connection:** JDBC → Redshift using `.env` variables.
- **Glue Script:** `ticket_management_system/glue_scripts/ticket_processing_job.py`
  - Extract: Read JSON from S3
  - Transform: Cast schema & validate no nulls
  - Load: COPY into Redshift
- **Schedule:** EventBridge rule triggers every 2 hours.
- **IAM:** S3 read/write, Redshift credentials, Glue service role.

### 10. CloudWatch Alarm (`_create_failure_alarm`)
- **Metric:** `AWS/States.ExecutionsFailed` for the state machine.
- **Threshold:** >0 failures in 1 minute.
- **Action:** Publish to SNS topic.

---

## 📂 Scripts & Code Samples

### `scripts/generate_ticket.py`
- **Purpose:** Generate realistic dummy tickets with LangChain + Bedrock, then push to Kinesis.
- **Key Steps:**
  1. Use `issue_scenarios` library to pick a product and issue type.
  2. Use `TicketGeneratorOutputParser` to format JSON ticket.
  3. Send `put_record` to `thesis-ticket-stream` with payload:
     ```json
     { "eventName": "TicketSubmitted", "ticketId": "TKT-...", "submittedAt": "ISO...", "data": {...} }
     ```

### Glue Script: `glue_scripts/ticket_processing_job.py`
- **get_ticket_schema():** Defines Spark schema for all fields.
- **read_tickets_from_s3():** Reads S3 JSON under `/tickets/`.
- **apply_schema_casting():** Cast raw types to proper Spark types.
- **validate_no_nulls():** Checks no required column is null.
- **write_to_redshift():** Uses `write_dynamic_frame.from_jdbc_conf` to load into Redshift.
- **process_tickets():** Orchestrates extract → transform → load.

### CDK Entry (`app.py` / `cdk.json`)
- **`app.py`:** Bootstraps the stack in your AWS account/region.
- **`cdk.json`:** Configuration for CDK commands.

---

## 🔧 Prerequisites & Setup

1. **AWS CLI** with proper IAM rights
2. **Node.js** (v16+) and **AWS CDK v2**
3. **Python 3.11** & virtual environment
4. **Docker** (optional, for local Lambda testing)

**Environment Variables** (`.env`):
```text
REDSHIFT_JDBC_CONNECTION_URL=
REDSHIFT_ARN=
REDSHIFT_USERNAME=
REDSHIFT_PASSWORD=
REDSHIFT_DATABASE=
REDSHIFT_SCHEMA=
REDSHIFT_TABLE=
REDSHIFT_SUBNET_ID=
REDSHIFT_SECURITY_GROUP_ID=
AVAILABILITY_ZONE=
AWS_REGION=us-east-1
```

**Install & Deploy:**
```bash
git clone ...
cd AWS-TicketManagementSystem
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
npm install -g aws-cdk
cdk bootstrap aws://<account>/<region>
cdk deploy
```

---

## 🔍 Testing & Validation
1. **Generate tickets:** `python scripts/generate_ticket.py`
2. **Monitor:** Kinesis, Lambda logs in CloudWatch
3. **Verify:** DynamoDB table entries & S3 JSON files
4. **Check ETL:** Glue job runs and data appears in Redshift
5. **Alarm:** Force a Step Function error to test SNS email

---

## 🧹 Cleanup
```bash
cdk destroy --force
```
All AWS resources will be removed, including data in DynamoDB, S3, Glue, etc.

