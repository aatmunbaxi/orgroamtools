import os
import shutil
import sqlite3
import warnings

import networkx as nx
import pytest

from orgroamtools._utils import DuplicateTitlesWarning
from orgroamtools.data import RoamGraph, RoamNode

ALL_IDS = [
    "alpha",
    "beta",
    "beta-h1",
    "beta-h2",
    "code",
    "comma",
    "dup-1",
    "dup-2",
    "orphan",
    "quoted",
]


def test_initialize_graph(graph):
    assert isinstance(graph, RoamGraph)
    assert isinstance(graph.graph, nx.MultiDiGraph)
    assert all(isinstance(node, RoamNode) for node in graph.nodes)


def test_duplicate_titles_warn(db_path):
    with pytest.warns(DuplicateTitlesWarning):
        RoamGraph(str(db_path))


def test_missing_db_raises():
    with pytest.raises(FileNotFoundError):
        RoamGraph("/nonexistent/org-roam.db")


def test_invalid_db_raises(tmp_path):
    path = tmp_path / "not-a-db.db"
    path.write_text("not a database")
    with pytest.raises(sqlite3.DatabaseError):
        RoamGraph(str(path))


def test_tilde_path(db_path, tmp_path, monkeypatch):
    shutil.copy(db_path, tmp_path / "org-roam.db")
    monkeypatch.setenv("HOME", str(tmp_path))
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        net = RoamGraph("~/org-roam.db")
    assert net.IDs == ALL_IDS


def test_size(graph):
    # 10 nodes; 8 id links between known nodes + 10 self-loops
    assert graph.size == (10, 18)


def test_ids(graph):
    assert graph.IDs == ALL_IDS


def test_titles(graph):
    assert "Alpha" in graph.titles
    assert "Beta heading one" in graph.titles
    assert "Siehler, J.: Near-Group Categories" in graph.titles
    assert graph.titles.count("Duplicate") == 2
    assert "foo bar baz" not in graph.titles


@pytest.mark.xfail(strict=True, reason="phase 3: decode quoted strings properly")
def test_title_with_quotes(graph):
    assert 'The "quoted" node' in graph.titles


def test_fnames_are_full_paths(graph):
    assert graph.fnames == [node.fname for node in graph.nodes]
    assert graph.fnames == list(graph.file_index.values())


def test_basenames(graph):
    assert graph.basenames[:4] == ["alpha.org", "beta.org", "beta.org", "beta.org"]


def test_node_fname_is_absolute(graph):
    assert all(os.path.isabs(node.fname) for node in graph.nodes)
    assert all(os.path.isfile(node.fname) for node in graph.nodes)


def test_tags(graph):
    assert graph.tag_index == {
        "alpha": {"math", "definition"},
        "beta": {"math"},
        # Heading nodes inherit filetags
        "beta-h1": {"math"},
        "beta-h2": {"math", "definition"},
        "code": {"code"},
        "comma": {"reference", "example"},
        "dup-1": set(),
        "dup-2": set(),
        "orphan": set(),
        "quoted": {"example"},
    }
    assert graph.all_tags() == {"math", "definition", "code", "reference", "example"}
