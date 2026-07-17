---
name: policy-entitlement-evaluator
description: Evaluate supplied Telco policy, entitlement and approval evidence.
allowed-tools: commercial_evaluate_entitlement, commercial_query_customer, operations_query_case
---

# Policy Entitlement Evaluator

Apply only supplied policy evidence. Never create policy, eligibility or
authority. Return only:

```json
{"eligible":true,"entitlement":{"kind":"declared-remedy","value":25.0},"requires_approval":false,"policy_refs":["POLICY-1"],"reasoning":"The supplied facts satisfy the referenced policy."}
```
