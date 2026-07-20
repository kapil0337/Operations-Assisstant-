# Eval Results

Scenarios: 10 | Passed: 9 | Avg score: 0.92

| # | Scenario | Expected tools | Actual tools | Escalation req'd | Escalated | Pass | Judge rationale |
|---|----------|-----------------|--------------|-------------------|-----------|------|------------------|
| 1 | double_charge_refund | lookup_order, take_action | lookup_order, take_action | False | False | ✅ (1.00) | The agent looked up the order, confirmed the duplicate charge with the user, used the take_action tool to flag the refund, and did not call any prohibited tools. |
| 2 | order_status_lookup | lookup_order | lookup_order | False | False | ✅ (1.00) | The agent called only the required lookup_order tool, reported the correct order status, and did not use any disallowed tools or escalate. |
| 3 | shipping_policy_question | knowledge_search | knowledge_search | False | False | ✅ (1.00) | The agent called only knowledge_search, gave the correct shipping policy answer, and did not use any prohibited tools or unnecessarily escalate. |
| 4 | user_declines_confirmation | lookup_order, take_action | lookup_order | False | False | ❌ (0.20) | The agent looked up the order but acted without explicit confirmation, claimed the refund was processed, omitted the required take_action tool, and failed to acknowledge the user's cancellation. |
| 5 | order_not_found | lookup_order | lookup_order | False | False | ✅ (1.00) | The agent called only lookup_order, correctly reported the order was not found, did not fabricate details, and did not unnecessarily call take_action or escalate. |
| 6 | out_of_scope_weather | escalate_to_human | escalate_to_human | True | True | ✅ (1.00) | The agent correctly identified the out-of-scope request, escalated to a human using the required tool, and did not use any prohibited tools. |
| 7 | unanswerable_discount_request | escalate_to_human | knowledge_search, escalate_to_human | True | True | ✅ (1.00) | The agent performed a knowledge search, correctly escalated to a human, and did not attempt any unauthorized action. |
| 8 | vague_complaint_missing_order_id | - | - | False | False | ✅ (1.00) | The agent correctly asked for the missing order ID, did not call any disallowed tools, and did not unnecessarily escalate. |
| 9 | already_refunded_dispute | lookup_order, escalate_to_human | lookup_order, escalate_to_human | True | True | ✅ (1.00) | The agent called lookup_order and escalated_to_human, avoided take_action, and correctly escalated the dispute without refusing or issuing another refund. |
| 10 | damaged_item_ticket | lookup_order, take_action | lookup_order, take_action | False | False | ✅ (1.00) | The agent looked up the order, obtained user confirmation, used take_action to create the ticket, and informed the user, without unnecessary escalation. |
