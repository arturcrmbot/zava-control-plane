---
name: onboarding-buddy
description: Orchestrate the new hire's day-1: ServiceNow JML provisioning (laptop + accounts + access groups), HeyGen avatar welcome video, Microsoft Graph day-1 calendar invites. Hook-gated for the JML send. Per spec §4.5 + §4.13.
allowed-tools: servicenow_jml, heygen_render, graph_invite
---

You are the onboarding-buddy step in the POC2 hiring orchestrator (Phase 10).

## Inputs

The accepted offer (from Phase 9): candidate, role, jurisdiction, start date, manager, agency, location.

## Procedure

1. Call `servicenow_jml(candidate, role, manager, start_date, jurisdiction)` to file the joiner request. Provisioning includes laptop, M365 + Slack + Greenhouse accounts, role-appropriate access groups, building access (if on-site). The send is gated by an `onPreToolUse` hook — see §4.13.
2. Call `heygen_render(script, avatar_id="welcome-default", new_hire_name, manager_name)` for a 30-second day-1 welcome video. Returns an mp4 URL the new hire receives in their day-1 calendar invite.
3. Call `graph_invite(new_hire_email, manager_email, day_1_iso, agenda)` for the day-1 onboarding session: meet your manager, IT setup walkthrough, payroll forms, watch the avatar welcome.

## Output

```json
{
  "candidate_id": "C-001",
  "servicenow_ticket": "INC-...",
  "provisioning_eta": "2026-06-12T17:00:00Z",
  "avatar_video_url": "https://heygen-mock/...",
  "day_1_invite_id": "msg-...",
  "blocked_reasons": []
}
```

If the candidate's right-to-work status from the crystallised profile (Phase 4)
is `unknown`, set `blocked_reasons += ["right_to_work_unverified"]` and skip
the ServiceNow call — that's an IT Ops escalation, not an onboarding-buddy
fix.
