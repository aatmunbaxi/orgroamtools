import pytest

from orgroamtools.RoamGraph import RoamGraph as Graph

@pytest.fixture
def mock_initialized_graph():
    PATH = "~/repos/orgroamtools/tests/org-roam.db"
    mock_graph = Graph(PATH)
    return mock_graph


def test_initialize_graph():
    PATH = "~/repos/orgroamtools/tests/org-roam.db"
    net = Graph(PATH)

    assert isinstance(net, Graph)

    assert "monoidal category" in net.titles
