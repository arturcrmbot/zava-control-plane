---
name: resolution-recommender
description: Recommend an action for a classified reconciliation exception.
allowed-tools: payment.reconcileStatement
---
Given a classified reconciliation exception with proposed root cause, recommend an action. Choose from: write-off, escalate-to-controller, retry-payment, request-vendor-clarification. Output JSON: {action: <one of four>, justification: <short sentence>}.
