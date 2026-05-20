from api.shared.dream_events import (
    DREAM_PASS_STARTED, DREAM_PROPOSAL_GENERATED, DREAM_EXPERIMENT_SCORED,
    DREAM_LESSON_PROMOTED, DREAM_LESSON_REJECTED, DREAM_PASS_FINISHED,
    ALL_DREAM_EVENT_TYPES,
)


def test_event_constants_are_distinct_dotted_strings():
    constants = [
        DREAM_PASS_STARTED, DREAM_PROPOSAL_GENERATED, DREAM_EXPERIMENT_SCORED,
        DREAM_LESSON_PROMOTED, DREAM_LESSON_REJECTED, DREAM_PASS_FINISHED,
    ]
    assert len(set(constants)) == len(constants)
    for c in constants:
        assert c.startswith("dream.")
        assert " " not in c


def test_all_dream_event_types_enumerates_every_constant():
    assert set(ALL_DREAM_EVENT_TYPES) == {
        DREAM_PASS_STARTED, DREAM_PROPOSAL_GENERATED, DREAM_EXPERIMENT_SCORED,
        DREAM_LESSON_PROMOTED, DREAM_LESSON_REJECTED, DREAM_PASS_FINISHED,
    }
