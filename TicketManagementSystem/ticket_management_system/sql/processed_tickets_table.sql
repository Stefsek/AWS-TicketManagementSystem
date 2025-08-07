-- ============================================================================
-- Redshift Table for Ticket Management System
-- ============================================================================
-- 
-- INSTRUCTIONS:
-- 1. Replace {REDSHIFT_WORKSPACE} with your actual Redshift schema name
-- 2. Replace {REDSHIFT_TABLE} with your desired table name
-- 
-- Examples:
--   - {REDSHIFT_WORKSPACE} →  analytics_schema, tickets_schema
--   - {REDSHIFT_TABLE} → processed_tickets, ticket_data, customer_tickets
-- 
-- Final example:
--   CREATE TABLE IF NOT EXISTS analytics_schema.processed_tickets (
-- ============================================================================

CREATE TABLE IF NOT EXISTS {REDSHIFT_WORKSPACE}.{REDSHIFT_TABLE} (
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

-- ============================================================================