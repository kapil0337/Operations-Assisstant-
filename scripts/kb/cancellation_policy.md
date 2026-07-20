# Order Cancellation Policy

Customers may request a cancellation before an order ships. Once an order status changes to
"shipped" or "delivered", cancellation is no longer possible — the customer must instead
request a return and refund after delivery.

## When cancellation is possible

- Order status is "processing" → cancellation is allowed. Use take_action with
  action_type "create_ticket" and reason "cancellation request" to open a cancellation
  ticket for the fulfilment team. The billing team will void the charge automatically
  once the cancellation is confirmed.
- Order status is "shipped" → cancellation is NOT possible via this system. Advise the
  customer to refuse delivery (item will be returned to warehouse) and then contact support
  for a refund once the return is logged.
- Order status is "delivered" → cancellation is NOT possible. The customer must initiate a
  return/refund request within the 30-day refund window.

## Same-day cancellation (within 2 hours of placing order)

Orders cancelled within 2 hours of placement are fully voided and no charge is applied.
The system does not currently expose order placement timestamps in the API — if the
customer says the order was placed very recently (within hours), open a cancellation ticket
with reason "same-day cancellation request" and note the customer's claim.

## Partial cancellations

For bundles or multi-item orders, partial cancellations are handled by the fulfilment team.
Open a ticket with reason "partial cancellation request" and specify which items the
customer wants to cancel.
