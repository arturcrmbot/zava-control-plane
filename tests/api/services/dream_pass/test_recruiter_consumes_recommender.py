from __future__ import annotations

from api.server.services import persona_responder


def _context(recommender_decision: str | None, voice_score: float = 0.75) -> dict:
    context = {
        'gate': 'post_voice',
        'screening': {'verdict': 'borderline'},
        'voice': {'score': voice_score},
    }
    if recommender_decision is not None:
        context['interview_recommender'] = {'decision': recommender_decision}
    return context


def _recruiter_decide(context: dict) -> dict:
    persona_responder.PERSONA_DEFINITIONS = persona_responder._load_personae()
    recruiter = persona_responder.PERSONA_DEFINITIONS['recruiter']
    return recruiter.decide(context)


def test_recruiter_uses_recommender_reject_over_voice_score() -> None:
    result = _recruiter_decide(_context('decline', voice_score=0.75))
    assert result['decision'] == 'reject'


def test_recruiter_uses_recommender_advance() -> None:
    result = _recruiter_decide(_context('advance', voice_score=0.2))
    assert result['decision'] == 'approve'


def test_recruiter_falls_back_when_no_recommender() -> None:
    result = _recruiter_decide(_context(None, voice_score=0.75))
    assert result['decision'] == 'approve'
