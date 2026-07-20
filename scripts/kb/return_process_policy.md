# Return Process Policy

## Eligibility

Items are returnable within 30 days of delivery if:
- The item is unused and in its original packaging (standard return).
- The item arrived damaged or defective (see Damaged Item Policy).
- The wrong item was delivered.

After 30 days, returns are not accepted through this helpdesk — escalate to a human if
the customer has a compelling reason outside this window (e.g. extended hospitalization).

## How to initiate a return

1. Look up the order to confirm it is in "delivered" status.
2. Open a support ticket via take_action (action_type "create_ticket",
   reason "return request — [brief reason]").
3. The warehouse team will email the customer a prepaid return label within 1 business day.
4. Once the item is received and inspected (typically 3–5 business days), a refund is
   issued to the original payment method within 5–7 business days.

## Already-refunded orders

If lookup_order or the tickets table shows a refund has already been issued for the order
(status "refunded" or a closed "refund" ticket exists), do NOT open a second return/refund
ticket. Explain the situation to the customer and escalate to a human if they dispute it.

## Digital products and software

Digital purchases (software keys, download codes) are non-returnable once delivered, as
they cannot be "returned". If the customer reports the key is invalid or the download is
corrupt, open a ticket with reason "defective digital product" and let the fulfilment team
issue a replacement key.
