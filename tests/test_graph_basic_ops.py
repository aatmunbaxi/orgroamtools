import pytest
import networkx as nx

from orgroamtools.RoamGraph import RoamGraph as Graph
from orgroamtools.RoamNode import RoamNode  as Node

@pytest.fixture
def mock_initialized_graph():
    PATH = "~/repos/orgroamtools/tests/org-roam.db"
    mock_graph = Graph(PATH)
    return mock_graph


def test_initialize_graph():
    PATH = "~/repos/orgroamtools/tests/org-roam.db"
    net = Graph(PATH)

    assert isinstance(net, Graph)


def test_graph_properties():
    PATH = "~/repos/orgroamtools/tests/org-roam.db"
    net = Graph(PATH)

    assert isinstance(net.graph, nx.MultiDiGraph)

    assert all(isinstance(s , str) for s in net.titles)
    assert "monoidal category" in net.titles
    assert not "foo bar baz" in net.titles

    # Platform dependent...
    assert all(isinstance(s , str) for s in net.fnames)

    assert all(isinstance(s , str) for s in net.IDs)


    assert all(isinstance(s[0], str) for s in net.links)
    mon_cat = net.node("monoidal category")
    assert isinstance(mon_cat, Node)
    assert net.node("representation of group").id in mon_cat.links
    assert all(isinstance(y, str) for s in  [a[1] for a in net.links] for y in s)

    assert net.node_title("monoidal category") == "monoidal category"
