# Refund Policy

Customers are eligible for a full refund within 30 days of purchase if the item is unused,
defective, or was never delivered. Refunds are processed back to the original payment
method and typically appear within 5-7 business days after approval.

An order can only be refunded once. If `charge_count` or refund history on an order shows
a refund has already been issued, do not flag a second refund -- explain this to the
customer and escalate to a human if they dispute it.

Refund requests should be flagged using the take_action tool with action_type
"flag_refund", which creates a ticket for the billing team to process. Always confirm the
order id and reason with the customer before flagging a refund.
