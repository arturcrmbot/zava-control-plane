# Threat 5: Real-Time Voice, Video & Avatar
**Severity: Medium**
**Refs: 14.1-14.4 (all Could Have), POC2 4.5**

## The Attack

POC2 requires live demonstration of:
- Screening call via voice: real-time STT, structured questions, transcription, scoring
- Multi-party video interview with agent as note-taker (Teams)
- Avatar-delivered personalised onboarding welcome video

GHCP SDK has no native voice/video capabilities. It's a text-in/text-out agentic runtime. The Pulse Agent interacts with Teams via Playwright DOM manipulation, not real-time audio/video streams.

All voice/video refs are "Could Have" in the questionnaire — but POC2 explicitly asks for live demo of voice screening and avatar video. This is a differentiator they'll judge live.

## The Mitigation Argument

- These are "Could Have" in the questionnaire
- MAI-Voice-1 and MAI-Transcribe-1 are GA April 2026
- Azure Communication Services handles real-time voice
- The GHCP SDK agent doesn't need to BE in the call — it can orchestrate: trigger call via ACS, receive transcript via webhook, process transcript in a session, output scores
- Avatar: HeyGen/Synthesia APIs are external services, agent generates the script + parameters, API generates the video
- Video note-taking: Teams meeting transcript API + post-meeting GHCP SDK session for summarisation

## Research Questions

1. Can Foundry Hosted Agents integrate with Azure Communication Services for real-time voice?
2. Is there an MCP server or tool pattern for MAI-Voice-1 / MAI-Transcribe-1?
3. How would a GHCP SDK agent orchestrate a voice screening call end-to-end?
4. For Teams video note-taking — is post-meeting transcript processing acceptable, or do they expect real-time in-meeting agent participation?
5. What's the simplest path to avatar video generation from a GHCP SDK session?
