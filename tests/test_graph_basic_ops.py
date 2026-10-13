import networkx as nx
import pytest

from orgroamtools._utils import DuplicateTitlesWarning, NodeNotFoundError
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


@pytest.mark.parametrize(
    "lookup",
    ["node", "node_links", "get_body", "get_latex_snippets", "get_src_blocks"],
)
def test_node_not_found(graph, lookup):
    with pytest.raises(NodeNotFoundError):
        getattr(graph, lookup)("nope")


def test_node_not_found_is_key_and_attribute_error(graph):
    # AttributeError kept for compatibility with code written before phase 3
    with pytest.raises(KeyError):
        graph.node("nope")
    with pytest.raises(AttributeError):
        graph.node("nope")


def test_node_title(graph):
    assert graph.node_title("beta-h1") == "Beta heading one"
    with pytest.raises(NodeNotFoundError):
        graph.node_title("Beta heading one")


def test_node_id(graph):
    assert graph.node_id("Siehler, J.: Near-Group Categories") == "comma"
    with pytest.raises(NodeNotFoundError):
        graph.node_id("comma")


def test_node_id_duplicate_title_warns(graph):
    with pytest.warns(DuplicateTitlesWarning):
        assert graph.node_id("Duplicate") == "dup-1"


# --- consistency -------------------------------------------------------------


def test_graph_setter_removed(graph):
    with pytest.raises(AttributeError):
        graph.graph = nx.MultiDiGraph()


def test_node_index_setter_rebuilds(graph):
    graph.node_index = {k: v for k, v in graph.node_index.items() if k != "beta-h1"}
    assert "beta-h1" not in graph.graph
    assert "beta-h1" not in graph.backlink_index["alpha"]
    assert "Beta heading one" not in graph.titles
    assert set(graph.graph.nodes) == set(graph.IDs)
    # alpha's only outgoing link was to beta-h1, but beta-h2 still links to it
    assert "alpha" not in {node.id for node in graph._orphans}


def test_refresh_deprecated_but_rebuilds(graph):
    # The in-place workflow documented in docs/source/index.rst
    index = graph.node_index
    del index["beta-h1"]
    with pytest.warns(DeprecationWarning):
        graph.refresh()
    assert "beta-h1" not in graph.graph
    assert "beta-h1" not in graph.node("alpha").backlinks
    assert set(graph.graph.nodes) == set(graph.IDs)


def test_duplicate_titles_index(graph):
    assert graph._duplicate_titles == ["Duplicate"]
    assert graph._contains_dup_titles



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


def test_remove_orphans_returns_copy(graph):
    result = graph.remove_orphans()
    assert result is not graph
    assert "orphan" in graph.IDs
    assert graph._orphans


def test_derived_collections_do_not_rewarn(graph, recwarn):
    graph.remove_orphans()
    graph.filter_tags(["math"])
    assert not [w for w in recwarn if w.category is DuplicateTitlesWarning]


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


def test_filter_tags_exclude_keeps_own_tags(graph):
    filtered = graph.filter_tags(["definition"], exclude=True)
    assert filtered.tag_index["code"] == {"code"}
    assert filtered.tag_index["comma"] == {"reference", "example"}


def test_filter_tags_include_graph_matches_nodes(graph):
    filtered = graph.filter_tags(["definition"], exclude=False)
    assert set(filtered.graph.nodes) == set(filtered.IDs)


def test_filter_tags_include_keeps_filter_tags(graph):
    filtered = graph.filter_tags(["definition"], exclude=False)
    assert filtered.tag_index == {
        "alpha": {"math", "definition"},
        "beta-h2": {"math", "definition"},
    }
    assert all(isinstance(tags, set) for tags in filtered.tag_index.values())


def test_filter_tags_accepts_any_iterable(graph):
    by_list = graph.filter_tags(["definition", "code"])
    by_gen = graph.filter_tags(tag for tag in ("definition", "code"))
    assert by_list.IDs == by_gen.IDs


def test_filter_tags_orphans(graph):
    # Without alpha and beta-h2, beta-h1 has nothing left to link to
    filtered = graph.filter_tags(["definition"], exclude=True)
    assert sorted(node.id for node in filtered._orphans) == [
        "beta",
        "beta-h1",
        "code",
        "orphan",
    ]


def test_filtered_nodes_are_independent(graph):
    filtered = graph.filter_tags(["definition"], exclude=True)
    filtered.node("code").tags.add("new")
    filtered.node("comma").backlinks.append("code")
    assert graph.node("code").tags == {"code"}
    assert graph.node("comma").backlinks == ["comma", "quoted"]
