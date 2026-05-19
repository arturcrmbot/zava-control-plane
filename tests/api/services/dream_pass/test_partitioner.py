from __future__ import annotations

import pytest

from api.server.services.dream_pass.partitioner import CorpusPartitioner


def test_partition_returns_n_unseen_ids(graph) -> None:
    available = [f'C-{i:03d}' for i in range(50)]
    partitioner = CorpusPartitioner(graph=graph, domain='hiring')

    split = partitioner.next_split(available=available, n=10)

    assert len(split.held_out_ids) == 10
    assert set(split.held_out_ids).issubset(set(available))
    assert split.already_used_ids == ()


def test_partition_excludes_already_used(graph) -> None:
    available = [f'C-{i:03d}' for i in range(50)]
    partitioner = CorpusPartitioner(graph=graph, domain='hiring')

    first = partitioner.next_split(available=available, n=10)
    partitioner.mark_used(experiment_id='EXP-1', persona_ids=first.held_out_ids, arm='control')

    second = partitioner.next_split(available=available, n=10)

    assert set(second.held_out_ids).isdisjoint(set(first.held_out_ids))
    assert set(second.already_used_ids) == set(first.held_out_ids)


def test_partition_raises_when_pool_exhausted(graph) -> None:
    available = ['C-001', 'C-002']
    partitioner = CorpusPartitioner(graph=graph, domain='hiring')
    first = partitioner.next_split(available=available, n=2)
    partitioner.mark_used(experiment_id='EXP-1', persona_ids=first.held_out_ids, arm='control')

    with pytest.raises(ValueError, match='insufficient unseen personas'):
        partitioner.next_split(available=available, n=1)
