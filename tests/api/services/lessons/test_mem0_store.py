from unittest.mock import MagicMock

import pytest


@pytest.mark.parametrize(
    ('missing_var', 'env'),
    [
        ('AZURE_OPENAI_ENDPOINT', {'AZURE_OPENAI_EMBED_DEPLOYMENT': 'text-embedding-3-large'}),
        ('AZURE_OPENAI_EMBED_DEPLOYMENT', {'AZURE_OPENAI_ENDPOINT': 'https://example.openai.azure.com'}),
    ],
)
def test_build_default_memory_requires_env(monkeypatch, missing_var, env) -> None:
    from api.server.services.lessons.mem0_store import build_default_memory

    monkeypatch.delenv('AZURE_OPENAI_ENDPOINT', raising=False)
    monkeypatch.delenv('AZURE_OPENAI_EMBED_DEPLOYMENT', raising=False)
    for key, value in env.items():
        monkeypatch.setenv(key, value)
    with pytest.raises(RuntimeError, match=missing_var):
        build_default_memory()


def test_build_default_memory_assembles_azure_chroma_config(monkeypatch, tmp_path) -> None:
    from api.server.services.lessons import mem0_store

    monkeypatch.setenv('AZURE_OPENAI_ENDPOINT', 'https://example.openai.azure.com')
    monkeypatch.setenv('AZURE_OPENAI_DEPLOYMENT', 'gpt-4o')
    monkeypatch.setenv('AZURE_OPENAI_EMBED_DEPLOYMENT', 'text-embedding-3-large')
    monkeypatch.setenv('AZURE_OPENAI_API_VERSION', '2024-10-21')
    monkeypatch.setenv('MEM0_CHROMA_DIR', str(tmp_path / 'chroma'))

    captured: dict[str, object] = {}

    class _FakeMemory:
        @classmethod
        def from_config(cls, config):
            captured['config'] = config
            return MagicMock(name='FakeMemory')

    monkeypatch.setattr('mem0.Memory', _FakeMemory)

    mem0_store.build_default_memory()

    config = captured['config']
    assert config['llm']['provider'] == 'azure_openai'
    assert config['llm']['config']['model'] == 'gpt-4o'
    assert config['llm']['config']['azure_kwargs']['azure_deployment'] == 'gpt-4o'
    assert config['llm']['config']['azure_kwargs']['azure_endpoint'] == 'https://example.openai.azure.com'
    assert config['embedder']['provider'] == 'azure_openai'
    assert config['embedder']['config']['model'] == 'text-embedding-3-large'
    assert config['embedder']['config']['embedding_dims'] == 3072
    assert config['vector_store']['provider'] == 'chroma'
    assert config['vector_store']['config']['collection_name'] == 'lesson_store'
    assert config['vector_store']['config']['path'] == str(tmp_path / 'chroma')
    assert (tmp_path / 'chroma').exists()
