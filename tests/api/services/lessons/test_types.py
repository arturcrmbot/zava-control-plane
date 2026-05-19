from api.server.services.lessons.types import LessonScope


def test_lesson_scope_requires_domain() -> None:
    scope = LessonScope(domain="hiring")
    assert scope.domain == "hiring"
    assert scope.persona_role is None
    assert scope.market is None


def test_lesson_scope_full() -> None:
    scope = LessonScope(domain="hiring", persona_role="recruiter", market="UK")
    assert scope.persona_role == "recruiter"
    assert scope.market == "UK"


def test_lesson_scope_matches_strict_when_equal() -> None:
    a = LessonScope(domain="hiring", persona_role="recruiter")
    b = LessonScope(domain="hiring", persona_role="recruiter")
    assert a.matches(b)


def test_lesson_scope_matches_broader_query() -> None:
    lesson_scope = LessonScope(domain="hiring")
    query_scope = LessonScope(domain="hiring", persona_role="recruiter")
    assert lesson_scope.matches(query_scope)


def test_lesson_scope_does_not_match_narrower() -> None:
    lesson_scope = LessonScope(domain="hiring", persona_role="recruiter")
    query_scope = LessonScope(domain="hiring")
    assert not lesson_scope.matches(query_scope)


def test_lesson_scope_cross_domain_never_matches() -> None:
    a = LessonScope(domain="hiring")
    b = LessonScope(domain="vendor_kyc")
    assert not a.matches(b)
    assert not b.matches(a)
