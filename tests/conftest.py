from pathlib import Path
import pytest

REPO_ROOT = Path(__file__).parent.parent
FIXTURES = Path(__file__).parent / "fixtures"

@pytest.fixture
def fixtures_dir():
    return FIXTURES

@pytest.fixture
def repo_root():
    return REPO_ROOT
