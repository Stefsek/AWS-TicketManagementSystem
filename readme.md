# AWS Ticket Management System (Thesis Project)

**Repository:** [Stefsek/AWS-TicketManagementSystem](https://github.com/Stefsek/AWS-TicketManagementSystem)

## Overview
This project uses AWS CDK (Python) to provision an end-to-end **ticket management system** for support workflows, including:

- **Kinesis Data Stream** for ticket ingestion
- **Lambda functions**:
  - **TriggerSFN**: Listens to Kinesis, filters for ticket submissions, and starts Step Functions
  - **ResponseGenerator**: Calls Bedrock LLM to generate customer responses and priority
  - **S3Writer**: Persists processed tickets to S3 in JSON format
- **DynamoDB** table to track metadata
- **SNS** topic for notifications and alarms
- **AWS Glue** job (Python/PySpark) for ETL into Redshift, scheduled every 2 hours
- **Step Functions** state machine to orchestrate ticket processing (sentiment → LLM → persistence → notify)
- **CloudWatch** alarm on Step Function failures routed via SNS

All resources use **RemovalPolicy.DESTROY** by default (suitable for dev/thesis) and sensitive configs are loaded from a `.env` file.

---

## Architecture Diagram (High-Level)
```
      ┌────────────┐         ┌────────────────┐
      │ Ticket Gen │ ───────▶│ Kinesis Stream │
      └────────────┘         └────────────────┘
                                     │
                                     ▼
                          ┌────────────────────────┐
                          │ TriggerSFN Lambda      │
                          │ (filter + start SFN)   │
                          └────────────────────────┘
                                     │
                                     ▼
                          ┌────────────────────────┐
                          │ Step Functions         │
                          │ 1. DetectSentiment     │
                          │ 2. ResponseGenerator   │
                          │ 3. Write to DynamoDB   │
                          │ 4. Publish SNS         │
                          │ 5. S3Writer Lambda     │
                          └────────────────────────┘
                                     │
                                     ▼
      ┌────────────┐           ┌──────────────┐
      │ DynamoDB   │◀──────────│ SNS Topic    │
      └────────────┘           └──────────────┘
           │                           │
           ▼                           ▼
      ┌────────────┐           ┌──────────────┐
      │ S3 Bucket  │           │ CloudWatch   │
      │ (JSON data)│           │ Alarm on SFN │
      └────────────┘           └──────────────┘
                                     │
                                     ▼
                              ┌──────────────┐
                              │ Glue ETL Job │
                              │ → Redshift   │
                              └──────────────┘
```

---

## Prerequisites

- **AWS CLI** configured with appropriate IAM credentials
- **Node.js** (for CDK toolkit)
- **Python 3.11**
- **AWS CDK v2** installed globally:
  ```bash
  npm install -g aws-cdk
  ```
- **Docker** (if you use Docker-backed Lambdas locally)

---

## Getting Started

1. **Clone the repo**
   ```bash
   git clone git@github.com:Stefsek/AWS-TicketManagementSystem.git
   cd AWS-TicketManagementSystem
   ```

2. **Create & populate `.env`** at project root:
   ```text
   # Redshift & networking
   REDSHIFT_JDBC_CONNECTION_URL=jdbc:redshift://<cluster>.<region>.redshift.amazonaws.com:5439/<database>
   REDSHIFT_ARN=arn:aws:redshift:<region>:<account>:cluster/<cluster>
   REDSHIFT_USERNAME=<username>
   REDSHIFT_PASSWORD=<password>
   REDSHIFT_DATABASE=<database>
   REDSHIFT_SCHEMA=<schema>
   REDSHIFT_TABLE=<table>
   REDSHIFT_SUBNET_ID=<subnet-id>
   REDSHIFT_SECURITY_GROUP_ID=<sg-id>
   AVAILABILITY_ZONE=<az>

   # Other env vars can be added as needed
   ```

3. **Install Python dependencies**
   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
   pip install -r requirements.txt
   ```

4. **Bootstrap your environment** (once per AWS account/region)
   ```bash
   cdk bootstrap aws://<account>/<region>
   ```

5. **Deploy the stack**
   ```bash
   cdk deploy
   ```

---

## Testing & Generating Dummy Tickets

Use the provided `scripts/generate_ticket.py` (or similar) to push dummy events into your Kinesis stream:
```bash
python scripts/generate_ticket.py
```
This uses your AWS credentials and `.env` to send realistic tickets, which trigger the full workflow.

---

## Project Structure

```
├── cdk.json                # CDK app config
├── app.py                  # CDK entrypoint
├── .env                    # Local env vars (excluded from git)
├── ticket_management_system/
│   ├── stack.py           # TicketManagementSystemStack
│   ├── lambdas/
│   │   ├── TriggerSFN/
│   │   ├── ResponseGenerator/
│   │   └── S3Writer/
│   ├── lambda_layers/     # Python dependencies for LLM
│   ├── glue_scripts/      # ETL job code
│   └── state_machine/     # ASL JSON definition
├── scripts/
│   └── generate_ticket.py # Dummy ticket generator
├── requirements.txt       # Python deps
└── README.md
```

---

## Cleanup
To tear down the environment and delete all resources:
```bash
cdk destroy
```  

