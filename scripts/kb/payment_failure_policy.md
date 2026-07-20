# Payment Failure and Billing Issue Policy

## Failed payment (order not placed)

If a customer reports their payment was declined and no order was created, this is an issue
with their bank or payment method — not with our system. Advise the customer to:
- Check that their card details are correct and not expired.
- Contact their bank to confirm no hold or block is in place.
- Retry the purchase with a different payment method if needed.

This helpdesk cannot process new payments or override declined transactions. If the customer
believes they were charged despite the order failing, look up the order with lookup_order.
If lookup_order returns not_found, there is no charge on our side — the hold (if any) was
placed by their bank and will release automatically within 3–5 business days.

## Charge appears but order is in "processing" state

A pending charge appearing on the customer's bank statement while the order is still
"processing" is normal — the payment was pre-authorized and will settle once the order ships.
This is not a double charge.

## Unexpected charge (no corresponding order)

If the customer reports a charge with no corresponding order in the system (lookup_order
returns not_found for any order ID they provide), escalate to a human billing specialist
with reason "unrecognized charge". This may indicate a billing system error or fraudulent
activity and requires manual investigation.

## Multiple payment methods

The system only records orders and their charge counts. It does not store payment method
details (card numbers, bank names). For questions about specific payment methods or card
statements, escalate to a human.
