# Shipping Policy

Standard shipping takes 5-7 business days within the country of purchase; expedited
shipping takes 1-2 business days. Orders show a `status` field (e.g. "processing",
"shipped", "delivered", "delayed") that reflects the current shipping state -- always
check lookup_order rather than guessing at delivery timelines.

If an order's status is "delayed" for more than 10 business days past the original
estimate, the customer is eligible to open a support ticket for investigation via
take_action (action_type "create_ticket") with reason "shipping delay".

Lost packages (status remains "shipped" with no movement for 14+ days) should be
escalated to a human, since they require carrier-side investigation outside this system.
