def extract_ticket_info(event: dict) -> dict:
    """
    Extracts the key fields from a nested ticket event dict into a flat dict.
    Returns:
        A flat dict with keys:
            subject, description, customer_name, company,
            sentiment, product, issue_type, ticket_id
    """
    ticket = event.get("ticket", {})
    data = ticket.get("data", {})
    contact = data.get("customer_contact_information", {})
    prod_info = data.get("product_issue_information", {})
    comp_result = event.get("ComprehendResult", {})

    return {
        "subject": data.get("subject"),
        "description": data.get("description"),
        "customer_name": contact.get("full_name"),
        "company": contact.get("company"),
        "sentiment": comp_result.get("Sentiment"),
        "product": prod_info.get("product"),
        "issue_type": prod_info.get("issue_type"),
        "ticket_id": ticket.get("ticketId"),
    }
