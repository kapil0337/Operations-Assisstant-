# Double-Charge / Duplicate Charge Policy

If a customer reports being charged more than once for the same order, check the order's
`charge_count` field via lookup_order. A `charge_count` greater than 1 confirms a duplicate
charge and the customer is entitled to a refund of the duplicate amount.

For confirmed duplicate charges:
1. Look up the order to confirm `charge_count` > 1.
2. Flag a refund via take_action (action_type "flag_refund") for the duplicate amount,
   citing "duplicate charge" as the reason.
3. Let the customer know the billing team will process the refund within 5-7 business
   days.

If `charge_count` is 1 (only a single charge on record) but the customer insists they were
double-charged, do not flag a refund based on their claim alone -- this likely requires
checking their bank/card statement, which is outside this system. Escalate to a human
billing specialist.
