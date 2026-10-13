import pytest


def test_heading_node_body(graph):
    assert graph.node_index["beta-h2"].body == "Heading two links back to Alpha."


def test_file_node_body(graph):
    body = graph.node_index["orphan"].body
    assert "This node links nowhere and nothing links to it." in body


def test_get_body_by_title(graph):
    assert graph.get_body("Beta heading two") == "Heading two links back to Alpha."


def test_get_body_by_id_matches_title(graph):
    assert graph.get_body("beta-h2") == graph.node("beta-h2").body


def test_body_index_covers_all_nodes(graph):
    index = graph.body_index
    assert set(index) == set(graph.IDs)
    assert all(isinstance(body, str) for body in index.values())


def test_math_snippet_index(graph):
    snippets = graph.math_snippet_index["alpha"]
    assert "a+b" in snippets
    assert "x^2" in snippets
    assert graph.math_snippet_index["orphan"] == []


@pytest.mark.xfail(strict=True, reason="phase 4: LaTeX regex misses starred envs")
def test_math_snippet_index_complete(graph):
    snippets = [s.strip() for s in graph.math_snippet_index["alpha"]]
    assert snippets == [
        "a+b",
        "c+d",
        "x^2",
        "e = mc^2",
        "f(x) = 0",
        "g &= h",
        "i + j",
    ]


def test_src_block_index(graph):
    blocks = graph.src_block_index["code"]
    assert ("python", 'print("hello")') in blocks
    assert ("emacs-lisp", '(message "hi")') in blocks
    assert graph.src_block_index["alpha"] == []


@pytest.mark.xfail(strict=True, reason="phase 4: src block without a language")
def test_src_block_index_complete(graph):
    assert graph.src_block_index["code"] == [
        ("python", 'print("hello")'),
        ("c++", "int x = 1;"),
        ("emacs-lisp", '(message "hi")'),
        (None, "no language"),
    ]


def test_get_latex_snippets_and_src_blocks_by_title(graph):
    assert graph.get_latex_snippets("Alpha") == graph.math_snippet_index["alpha"]
    assert graph.get_src_blocks("Code") == graph.src_block_index["code"]
