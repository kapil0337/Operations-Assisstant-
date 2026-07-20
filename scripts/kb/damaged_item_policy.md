# Damaged or Defective Item Policy

If a customer reports receiving a damaged, defective, or incorrect item, they are eligible
for a full refund or replacement within 30 days of the order's delivery date.

## Steps to handle a damaged item claim

1. Use lookup_order to confirm the order status is "delivered".
2. If the item was delivered and the customer reports damage, open a support ticket via
   take_action (action_type "create_ticket", reason "damaged item received"). This triggers
   the warehouse team to initiate a replacement or refund process.
3. Inform the customer they do not need to return the damaged item unless the warehouse
   team specifically requests it.
4. Refunds for damaged items are typically processed within 5–7 business days after the
   ticket is reviewed. Replacements ship within 2–3 business days.

## What is NOT covered

- Normal wear and tear after extended use.
- Customer-induced damage (dropped, water damaged, etc.) — these are out of scope for
  this helpdesk. Escalate to a human if the customer disputes whether damage was pre-existing.
- Items reported as damaged more than 30 days after delivery — escalate to a human.

## Defective items (stops working after initial use)

A defective item (one that works briefly then fails) is treated the same as a damaged item
for the first 30 days. After 30 days, the warranty team handles claims — escalate to a
human agent with "warranty claim" as the reason.
