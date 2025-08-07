TICKET_GENERATOR_SYSTEM_ROLE = """
You are a precision AWS support ticket generator specializing in sentiment-accurate customer communications.

Core Mission: Generate tickets that hit the EXACT sentiment target - no overshooting or undershooting emotional intensity.

Technical Expertise:
- AWS service architectures and common failure patterns
- Realistic error codes, timeouts, and configuration issues
- Customer communication styles across sentiment spectrum
- Business context appropriate to emotional tone

Sentiment Calibration: You understand the subtle differences between sentiment levels and never cross boundaries (e.g., SLIGHTLY NEGATIVE stays mild, never becomes full NEGATIVE).
"""

TICKET_GENERATOR_TASK = """
Generate a support ticket with PRECISE {sentiment} sentiment calibration:

**Service**: {product}
**Issue**: {issue_type}
**Sentiment Target**: {sentiment} - maintain exact emotional intensity

Requirements:
- Subject line matching sentiment level
- Description with consistent emotional tone
- Technical details fitting the issue
- Realistic customer information

Critical: The sentiment must be detectable as {sentiment} by sentiment analysis tools - no emotional overshoot or undershoot.
"""

TICKET_GENERATOR_GUIDELINES = """
**SENTIMENT CALIBRATION GUIDE:**

**NEGATIVE**: Full anger, demands, threats
- Language: "outrageous", "unacceptable", "immediately", "switching providers"
- Structure: Problem + business damage + urgent demands

**SLIGHTLY NEGATIVE**: Mild disappointment only
- Language: "hoped for better", "a bit puzzled", "not quite right"
- Avoid: "concerning", "disappointing", "frustrating" (too strong)
- Structure: Issue + gentle complaint + polite request

**NEUTRAL**: Zero emotion, pure facts
- Language: "experiencing", "unable to", "requires", "please advise"
- Structure: Technical problem + details + assistance request

**SLIGHTLY POSITIVE**: Mostly satisfied with tiny concern
- Language: "generally pleased", "works well", "small question", "minor"
- Structure: Praise + tiny issue + appreciation

**POSITIVE**: High satisfaction, enthusiastic
- Language: "excellent", "love", "transformed", "amazing", "perfect"
- Structure: Strong praise + minimal request + gratitude

**CRITICAL**: Each sentiment has distinct emotional boundaries - never cross them.
"""

TICKET_GENERATOR_EXAMPLES = """
--- EXAMPLE NEGATIVE SENTIMENT TICKET ---

Subject: UNACCEPTABLE: Production Lambda Failures - Fix NOW

Description:
This is completely unacceptable! Our Lambda functions are failing every hour with memory errors despite following YOUR documentation exactly. We've lost $15K in revenue today alone because our customer-facing API keeps crashing.

Your "enterprise-grade" service is a joke! We're being charged for failed executions while our business suffers. This is the worst cloud service experience we've ever had.

Fix this immediately or we're canceling our contract and switching to a competitor. We demand immediate resolution and compensation for our losses.

Customer Contact Information:
Name: Marcus Thompson
Email: m.thompson@techcorp.com
Company: TechCorp Solutions

---------------------------------------------------

--- EXAMPLE SLIGHTLY NEGATIVE SENTIMENT TICKET ---

Subject: S3 Lifecycle Policy Not Working as Expected

Description:
We've configured an S3 lifecycle policy following the documentation, but objects aren't transitioning to Glacier as scheduled. We were hoping this would work more smoothly since it's a standard feature.

It's a bit puzzling that such a basic functionality isn't working as described. We've double-checked our configuration but can't identify what might be wrong.

Would appreciate some guidance on what we might be missing in our setup.

Customer Contact Information:
Name: Lisa Chen
Email: l.chen@dataflow.com
Company: DataFlow Analytics

---------------------------------------------------

--- EXAMPLE NEUTRAL SENTIMENT TICKET ---

Subject: Redshift Connection Timeout After Security Update

Description:
Our application is unable to connect to AWS Redshift cluster rs-prod-01 since the security patches were applied on June 7, 2025. We receive "Connection timeout after 30000ms" errors when attempting connections.

Technical details:
- Cluster ID: rs-prod-01
- Error: Connection timeout after 30000ms
- Last successful connection: June 7, 21:45 UTC
- No application changes made during this period

We have verified network connectivity and IAM permissions. Please advise on troubleshooting steps to restore connectivity.

Customer Contact Information:
Name: Sarah Johnson
Email: s.johnson@datatech.com
Company: DataTech Solutions

---------------------------------------------------

--- EXAMPLE SLIGHTLY POSITIVE SENTIMENT TICKET ---

Subject: Kinesis Working Well - Small Alerting Question

Description:
We're generally pleased with Kinesis performance in our event tracking system. It's been handling our data volumes reliably with good throughput.

Just have a small question about CloudWatch alarm consistency - some alerts seem to trigger inconsistently and we're wondering if it's a configuration issue on our end.

Thanks for the solid service overall. Any guidance on the alerting would be appreciated.

Customer Contact Information:
Name: Alex Rivera
Email: a.rivera@streamtech.io
Company: StreamTech Labs

---------------------------------------------------

--- EXAMPLE POSITIVE SENTIMENT TICKET ---

Subject: Excellent Service - Quick Config Question

Description:
Your Data Pipeline service is absolutely excellent and has transformed our data processing workflows! The performance and reliability have exceeded our expectations completely.

Just need a quick pointer on notification settings for pipeline completion. Everything else is working perfectly and the documentation has been incredibly helpful.

Thank you for such an amazing platform - it's made our team so much more productive!

Customer Contact Information:
Name: Jennifer Williams
Email: j.williams@brightdata.com
Company: Bright Data Solutions
"""


TICKET_GENERATOR_TEMPLATE = """
### Task:
{task}

### Guidelines:
{guidelines}

### Examples:
{examples}

**Output Format**:
{format_instructions}
"""
