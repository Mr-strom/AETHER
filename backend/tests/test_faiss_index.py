"""Unit tests for backend/services/index/faiss_index.py"""

from pathlib import Path

import numpy as np
import pytest

try:
    import faiss
    FAISS_AVAILABLE = True
except ImportError:
    FAISS_AVAILABLE = False

pytestmark = pytest.mark.skipif(
    not FAISS_AVAILABLE, reason="faiss-cpu not installed"
)

DIM = 1024


def _rand_vecs(n: int, dim: int = DIM) -> np.ndarray:
    """Generate L2-normalised random float32 vectors."""
    vecs = np.random.rand(n, dim).astype("float32")
    norms = np.linalg.norm(vecs, axis=1, keepdims=True)
    return vecs / (norms + 1e-10)


# ---------------------------------------------------------------------------
# FAISSIndexService tests
# ---------------------------------------------------------------------------


def test_initial_total_vectors_zero() -> None:
    from backend.services.index.faiss_index import FAISSIndexService

    svc = FAISSIndexService(dim=DIM)
    assert svc.total_vectors == 0


def test_add_vectors_updates_count() -> None:
    from backend.services.index.faiss_index import FAISSIndexService

    svc = FAISSIndexService(dim=DIM)
    vecs = _rand_vecs(5)
    svc.add_vectors(vecs, ids=[1, 2, 3, 4, 5])
    assert svc.total_vectors == 5


def test_add_vectors_mismatched_ids_raises() -> None:
    from backend.services.index.faiss_index import FAISSIndexService

    svc = FAISSIndexService(dim=DIM)
    vecs = _rand_vecs(3)
    with pytest.raises(ValueError, match="ids length"):
        svc.add_vectors(vecs, ids=[1, 2])  # 2 ids for 3 vectors


def test_add_vectors_wrong_dim_raises() -> None:
    from backend.services.index.faiss_index import FAISSIndexService

    svc = FAISSIndexService(dim=DIM)
    wrong = _rand_vecs(3, dim=512)
    with pytest.raises(ValueError, match="Expected shape"):
        svc.add_vectors(wrong, ids=[1, 2, 3])


def test_search_returns_correct_ids() -> None:
    from backend.services.index.faiss_index import FAISSIndexService

    svc = FAISSIndexService(dim=DIM)
    vecs = _rand_vecs(10)
    evidence_ids = list(range(100, 110))
    svc.add_vectors(vecs, ids=evidence_ids)

    # The closest vector to itself should be itself
    dists, ids = svc.search(vecs[0], k=1)
    assert len(ids) == 1
    assert ids[0] == 100  # maps back to evidence_id 100


def test_search_top_k(tmp_path: Path) -> None:
    from backend.services.index.faiss_index import FAISSIndexService

    svc = FAISSIndexService(dim=DIM)
    vecs = _rand_vecs(20)
    svc.add_vectors(vecs, ids=list(range(20)))

    dists, ids = svc.search(vecs[5], k=5)
    assert len(ids) == 5
    assert 5 in ids  # The query itself must be in top-5


def test_search_k_exceeds_total(tmp_path: Path) -> None:
    """When k > total_vectors, FAISS clamps to total_vectors."""
    from backend.services.index.faiss_index import FAISSIndexService

    svc = FAISSIndexService(dim=DIM)
    vecs = _rand_vecs(3)
    svc.add_vectors(vecs, ids=[10, 20, 30])

    dists, ids = svc.search(vecs[0], k=50)
    assert len(ids) <= 3


def test_search_empty_index_returns_empty() -> None:
    from backend.services.index.faiss_index import FAISSIndexService

    svc = FAISSIndexService(dim=DIM)
    dists, ids = svc.search(_rand_vecs(1)[0], k=5)
    assert dists == []
    assert ids == []


def test_save_and_load(tmp_path: Path) -> None:
    from backend.services.index.faiss_index import FAISSIndexService

    index_path = tmp_path / "test.faiss"

    svc1 = FAISSIndexService(dim=DIM, index_path=index_path)
    vecs = _rand_vecs(5)
    svc1.add_vectors(vecs, ids=[10, 20, 30, 40, 50])
    svc1.save()

    svc2 = FAISSIndexService(dim=DIM, index_path=index_path)
    svc2.load()

    assert svc2.total_vectors == 5

    # Search should return the same top result
    dists1, ids1 = svc1.search(vecs[0], k=1)
    dists2, ids2 = svc2.search(vecs[0], k=1)
    assert ids1 == ids2


def test_load_missing_faiss_file(tmp_path: Path) -> None:
    from backend.services.index.faiss_index import FAISSIndexService

    svc = FAISSIndexService(dim=DIM, index_path=tmp_path / "missing.faiss")
    with pytest.raises(FileNotFoundError):
        svc.load()


def test_load_missing_ids_file(tmp_path: Path) -> None:
    from backend.services.index.faiss_index import FAISSIndexService

    index_path = tmp_path / "idx.faiss"
    # Write a valid FAISS index but no .ids file
    idx = faiss.IndexFlatIP(DIM)
    faiss.write_index(idx, str(index_path))

    svc = FAISSIndexService(dim=DIM, index_path=index_path)
    with pytest.raises(FileNotFoundError, match=".ids"):
        svc.load()


def test_save_nothing_if_not_initialised(tmp_path: Path) -> None:
    from backend.services.index.faiss_index import FAISSIndexService

    svc = FAISSIndexService(dim=DIM, index_path=tmp_path / "noop.faiss")
    # Should log a warning and not crash
    svc.save()
    assert not (tmp_path / "noop.faiss").exists()


def test_1d_query_vector_accepted() -> None:
    """Search should accept a 1-D query vector and reshape it internally."""
    from backend.services.index.faiss_index import FAISSIndexService

    svc = FAISSIndexService(dim=DIM)
    vecs = _rand_vecs(3)
    svc.add_vectors(vecs, ids=[1, 2, 3])

    flat_query = vecs[0].flatten()  # Shape (1024,)
    dists, ids = svc.search(flat_query, k=1)
    assert len(ids) == 1
