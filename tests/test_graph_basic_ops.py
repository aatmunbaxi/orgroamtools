import networkx as nx
import pytest

from orgroamtools._utils import DuplicateTitlesWarning
from orgroamtools.data import OrgLink, RoamGraph, RoamNode

# --- links -------------------------------------------------------------------


def test_links(graph):
    # Every node links to itself; links to unknown IDs are dropped
    assert graph.backlink_index == {
        "alpha": ["alpha", "beta-h1"],
        "beta": ["beta"],
        "beta-h1": ["beta-h1", "beta-h2"],
        "beta-h2": ["beta-h2", "alpha"],
        "code": ["code", "alpha"],
        "comma": ["comma", "quoted"],
        "dup-1": ["dup-1", "alpha"],
        "dup-2": ["dup-2", "dup-1"],
        "orphan": ["orphan"],
        "quoted": ["quoted", "alpha"],
    }


def test_adjacency_list(graph):
    adj = graph.adjacency_list
    assert ["alpha", "beta-h1"] in adj
    assert ["alpha", "alpha"] in adj
    assert ["alpha", "does-not-exist"] not in adj
    assert len(adj) == graph.size[1]


def test_graph_matches_links(graph):
    assert set(graph.graph.nodes) == set(graph.IDs)
    assert nx.number_of_selfloops(graph.graph) == len(graph.IDs)
    assert graph.graph.has_edge("beta-h2", "alpha")
    assert not graph.graph.has_edge("alpha", "beta-h2")


def test_node_links(graph):
    assert graph.node_links("alpha") == ["alpha", "beta-h1"]
    assert graph.node_links("Alpha") == ["alpha", "beta-h1"]
    with pytest.raises(AttributeError):
        graph.node_links("nope")


def test_misc_links(graph):
    assert graph.misc_links["beta"] == []
    assert all(isinstance(link, OrgLink) for link in graph.misc_links["alpha"])


@pytest.mark.xfail(strict=True, reason="phase 3: comma in link destination splits it")
def test_misc_links_with_comma(graph):
    assert graph.misc_links["alpha"] == [
        OrgLink("https", "//example.com/a,b", None),
        OrgLink("file", "figures/alpha.png", None),
    ]


def test_misc_link_index(graph):
    assert all(
        isinstance(link, OrgLink)
        for links in graph.misc_link_index.values()
        for link in links
    )
    assert graph.misc_link_index == graph.misc_links


# --- lookup ------------------------------------------------------------------


def test_node_by_title(graph):
    node = graph.node("Alpha")
    assert isinstance(node, RoamNode)
    assert node.id == "alpha"
    assert "beta-h1" in node.backlinks


def test_node_by_duplicate_title_warns(graph):
    with pytest.warns(DuplicateTitlesWarning):
        assert graph.node("Duplicate").id == "dup-1"


def test_node_by_id(graph):
    assert graph.node("alpha").title == "Alpha"
    assert graph.node("dup-2").title == "Duplicate"


def test_node_not_found(graph):
    with pytest.raises(AttributeError):
        graph.node("nope")


def test_node_title(graph):
    assert graph.node_title("beta-h1") == "Beta heading one"
    with pytest.raises(AttributeError):
        graph.node_title("Beta heading one")


def test_node_id(graph):
    assert graph.node_id("Siehler, J.: Near-Group Categories") == "comma"
    with pytest.raises(AttributeError):
        graph.node_id("comma")


def test_id_title_map(graph):
    assert list(graph.id_title_map.keys()) == graph.IDs
    assert graph.id_title_map["beta-h2"] == "Beta heading two"


# --- orphans -----------------------------------------------------------------


def test_orphans(graph):
    # "beta" is a file node whose headings are linked, but nothing links to it
    assert sorted(node.id for node in graph._orphans) == ["beta", "orphan"]
    assert graph._is_connected is False


def test_remove_orphans_removes(graph):
    expected = [i for i in graph.IDs if i not in {"beta", "orphan"}]
    result = graph.remove_orphans()
    assert result.IDs == expected
    assert result._is_connected


@pytest.mark.xfail(strict=True, reason="phase 3: remove_orphans should return a copy")
def test_remove_orphans_returns_copy(graph):
    result = graph.remove_orphans()
    assert result is not graph
    assert "orphan" in graph.IDs


def test_remove_orphans_keeps_misc_links(graph):
    before = graph.misc_links["alpha"]
    result = graph.remove_orphans()
    assert result.misc_links["alpha"] == before


def test_remove_orphans_keeps_full_paths(graph):
    before = graph.file_index
    result = graph.remove_orphans()
    assert all(result.file_index[i] == before[i] for i in result.IDs)
    assert "Heading two links back to Alpha." in result.node_index["beta-h2"].body


# --- filter_tags -------------------------------------------------------------


def test_filter_tags_exclude_nodes(graph):
    filtered = graph.filter_tags(["definition"], exclude=True)
    assert isinstance(filtered, RoamGraph)
    assert filtered is not graph
    assert filtered.IDs == [
        "beta",
        "beta-h1",
        "code",
        "comma",
        "dup-1",
        "dup-2",
        "orphan",
        "quoted",
    ]
    # Original untouched
    assert "alpha" in graph.IDs


def test_filter_tags_exclude_drops_links_to_excluded(graph):
    filtered = graph.filter_tags(["definition"], exclude=True)
    assert "beta-h2" not in filtered.node("Beta heading one").backlinks
    assert set(filtered.graph.nodes) == set(filtered.IDs)


def test_filter_tags_include_nodes(graph):
    filtered = graph.filter_tags(["definition"], exclude=False)
    assert filtered.IDs == ["alpha", "beta-h2"]


@pytest.mark.xfail(strict=True, reason="phase 3: filter_tags misaligns tags")
def test_filter_tags_exclude_keeps_own_tags(graph):
    filtered = graph.filter_tags(["definition"], exclude=True)
    assert filtered.tag_index["code"] == {"code"}
    assert filtered.tag_index["comma"] == {"reference", "example"}


@pytest.mark.xfail(strict=True, reason="phase 3: include mode leaves ghost graph nodes")
def test_filter_tags_include_graph_matches_nodes(graph):
    filtered = graph.filter_tags(["definition"], exclude=False)
    assert set(filtered.graph.nodes) == set(filtered.IDs)
