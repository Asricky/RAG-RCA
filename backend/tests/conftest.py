import os
import pytest

# Tests never read or mutate the developer's application database.
os.environ["APP_ENV"] = "test"
os.environ["DATABASE_URL"] = "sqlite://"
os.environ["JWT_SECRET"] = "test-only-secret-with-at-least-32-characters"
os.environ["LLM_PROVIDER"] = "mock"
os.environ["KPI_SOURCE"] = "demo"


@pytest.fixture(autouse=True)
def stub_opensearch_retrieval(monkeypatch):
    from app.services.log_store import log_store
    from tests.search_stub import SearchStub

    def search(*args, **kwargs):
        return SearchStub(log_store.logs).hybrid_search(*args, **kwargs)

    monkeypatch.setattr(log_store, "hybrid_search", search)
