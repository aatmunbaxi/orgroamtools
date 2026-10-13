from pathlib import Path

import orgparse
import pytest

from orgroamtools._utils import BodyNotFoundWarning
from orgroamtools.data import RoamNode, _parse_bodies

ROAM_DIR = Path(__file__).parent / "fixtures" / "roam"


def make_node(path, node_id="n"):
    return RoamNode(node_id, "N", str(path), set(), [node_id], [])


# --- body semantics ----------------------------------------------------------


def test_heading_node_body(graph):
    assert graph.node_index["beta-h2"].body == "Heading two links back to Alpha."


def test_file_node_body(graph):
    assert (
        graph.node_index["orphan"].body
        == "This node links nowhere and nothing links to it."
    )


def test_file_node_body_includes_child_headings(graph):
    assert graph.node_index["beta"].body == (
        "Beta is a file-level node containing two heading-level nodes.\n"
        "* Beta heading one\n"
        "Heading one links to Beta heading two.\n"
        "* Beta heading two\n"
        "Heading two links back to Alpha."
    )


def test_file_keywords_stripped(graph):
    for node_id in ("alpha", "beta", "code", "quoted"):
        assert not graph.node_index[node_id].body.startswith("#+")


def test_links_rendered_as_descriptions(graph):
    assert graph.node_index["beta-h1"].body == "Heading one links to Beta heading two."


def test_leading_src_block_is_not_a_keyword(tmp_path):
    path = tmp_path / "n.org"
    path.write_text(
        ":PROPERTIES:\n:ID: n\n:END:\n#+title: N\n#+begin_src python\nx\n#+end_src\n"
    )
    assert make_node(path).body == "#+begin_src python\nx\n#+end_src"


def test_nested_heading_levels(tmp_path):
    path = tmp_path / "n.org"
    path.write_text(
        "* Top\n:PROPERTIES:\n:ID: n\n:END:\ntop text\n** Child\nchild text\n"
        "*** Grandchild\n"
    )
    assert make_node(path).body == "top text\n** Child\nchild text\n*** Grandchild"


def test_get_body_by_title(graph):
    assert graph.get_body("Beta heading two") == "Heading two links back to Alpha."


def test_get_body_by_id_matches_title(graph):
    assert graph.get_body("beta-h2") == graph.node("beta-h2").body


def test_body_index_covers_all_nodes(graph):
    index = graph.body_index
    assert list(index) == graph.IDs
    assert index == {node.id: node.body for node in graph.nodes}


# --- missing bodies ----------------------------------------------------------


def test_missing_id_warns(recwarn):
    node = make_node(ROAM_DIR / "alpha.org", node_id="not-in-file")
    with pytest.warns(BodyNotFoundWarning, match="not-in-file"):
        assert node.body == ""


def test_missing_file_warns(tmp_path):
    node = make_node(tmp_path / "deleted.org")
    with pytest.warns(BodyNotFoundWarning, match="deleted.org"):
        assert node.body == ""


# --- caching -----------------------------------------------------------------


def test_each_file_parsed_once(graph, monkeypatch):
    _parse_bodies.cache_clear()
    loaded = []
    real_load = orgparse.load

    def counting_load(path, *args, **kwargs):
        # load(path) opens the file and calls load(file) again
        if isinstance(path, str):
            loaded.append(path)
        return real_load(path, *args, **kwargs)

    monkeypatch.setattr(orgparse, "load", counting_load)
    _ = graph.body_index, graph.math_snippet_index, graph.src_block_index
    _ = [node.body for node in graph.nodes]
    assert sorted(loaded) == sorted(set(graph.fnames))


def test_body_follows_file_changes(tmp_path):
    path = tmp_path / "n.org"
    path.write_text(":PROPERTIES:\n:ID: n\n:END:\n#+title: N\n\nfirst\n")
    node = make_node(path)
    assert node.body == "first"
    path.write_text(":PROPERTIES:\n:ID: n\n:END:\n#+title: N\n\nsecond version\n")
    assert node.body == "second version"


# --- extraction --------------------------------------------------------------


def test_math_snippet_index(graph):
    assert graph.math_snippet_index["alpha"] == [
        "a+b",
        "c+d",
        "x^2",
        "e = mc^2",
        "f(x) = 0",
        "g &= h",
        "i + j",
    ]
    assert graph.math_snippet_index["orphan"] == []


def test_src_block_index(graph):
    assert graph.src_block_index["code"] == [
        ("python", 'print("hello")'),
        ("c++", "int x = 1;"),
        ("emacs-lisp", '(message "hi")'),
        (None, "no language"),
    ]
    assert graph.src_block_index["alpha"] == []


def test_get_latex_snippets_and_src_blocks_by_title(graph):
    assert graph.get_latex_snippets("Alpha") == graph.math_snippet_index["alpha"]
    assert graph.get_src_blocks("Code") == graph.src_block_index["code"]
