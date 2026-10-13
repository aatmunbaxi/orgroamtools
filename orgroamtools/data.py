from __future__ import annotations

import os
import re
import sqlite3 as sql
import warnings
from collections import defaultdict
from collections.abc import Iterable
from contextlib import closing
from dataclasses import dataclass, replace
from functools import lru_cache
from itertools import islice
from pathlib import Path

import networkx as nx
import orgparse as op

from orgroamtools._utils import (
    BodyNotFoundWarning,
    DuplicateTitlesWarning,
    IdentifierType,  # noqa: F401  (kept importable from here; unused since phase 3)
    NodeNotFoundError,
    decode_lisp_string,
    extract_math_snippets,
    extract_src_blocks,
)


@dataclass
class RoamNode:
    """Store relevant org-roam node information

    A node is an atomic note known to the org-roam database.
    It is uniquely determined by an ID generated at the time of creation, but
    has other identifiers and information that a user might want to know about.

    Attributes
    ----------
    id : ``str``
        Unique org ID of org-roam node
    title : ``str``
        Title of org-roam node
    fname : ``str``
        Filename of org-roam node
    tags : ``set[str]``
        Collection of tags of org-roam node
    backlinks : ``list[str]``
        List of backlinks in org-roam node
    misc_links : ``list[OrgLink]``
        List of miscellaneous links that are not links to other nodes
    """

    id: str
    title: str
    fname: str
    tags: set[str]
    backlinks: list[str]
    misc_links: list[OrgLink]

    @property
    def body(self) -> str:
        """Return body of node

        The node's text and that of its subheadings, including the subheadings'
        heading lines. The node's own heading line, its property drawer, and a
        file's leading ``#+keyword:`` lines are omitted. Links are rendered as
        their descriptions. The file is parsed on first access and cached until it
        changes on disk.

        Returns
        -------
        ``str``
            Body text of node, or ``""`` if it could not be read

        Warns
        -----
        BodyNotFoundWarning
            If the node's file is missing or no longer contains the node's ID
        """
        return _lookup_body(self.id, self.fname, _file_bodies(self.fname))


# Leading "#+title:", "#+filetags:" etc. of a file; duplicates node fields
FILE_KEYWORDS_RE = re.compile(r"\A(?:[ \t]*(?:\#\+\w+:[^\n]*)?\n)*")


def _subtree_text(node: op.node.OrgBaseNode) -> str:
    """Text of ``node`` and its descendants, with descendant heading lines.

    The node's own heading line and property drawer are not included, nor are
    the leading keyword lines of a file.
    """
    own = node.get_body()
    if node.is_root():
        own = FILE_KEYWORDS_RE.sub("", own)
    parts = [own]
    for child in islice(node, 1, None):
        parts.append(f"{'*' * child.level} {child.heading}")
        parts.append(child.get_body())
    return "\n".join(part.strip("\n") for part in parts if part.strip()).strip()


@lru_cache(maxsize=256)
def _parse_bodies(path: str, mtime_ns: int, size: int) -> dict[str, str]:
    """Bodies of all nodes in a file, by ID. Cached per file version."""
    bodies = {}
    for node in op.load(path):
        node_id = node.get_property("ID")
        if node_id:
            bodies[node_id] = _subtree_text(node)
    return bodies


def _file_bodies(path: str) -> dict[str, str] | None:
    """Bodies of all nodes in a file by ID, or ``None`` if the file is missing."""
    try:
        stat = os.stat(path)
    except FileNotFoundError:
        return None
    return _parse_bodies(path, stat.st_mtime_ns, stat.st_size)


def _lookup_body(node_id: str, path: str, bodies: dict[str, str] | None) -> str:
    if bodies is None:
        message = f"File of node {node_id} not found: {path}"
    elif node_id not in bodies:
        message = f"No heading with ID {node_id} in {path}"
    else:
        return bodies[node_id]
    warnings.warn(message, BodyNotFoundWarning, stacklevel=3)
    return ""


def _load_nodes(db_path: str) -> dict[str, RoamNode]:
    """Read all nodes from an org-roam database, ordered by ID.

    Links to IDs that are not in the database are dropped. By convention each
    node links to itself first.
    """
    uri = f"{Path(db_path).resolve().as_uri()}?mode=ro"
    with closing(sql.connect(uri, uri=True)) as con:
        node_rows = con.execute(
            "SELECT id, file, title FROM nodes ORDER BY id ASC"
        ).fetchall()
        tag_rows = con.execute("SELECT node_id, tag FROM tags").fetchall()
        link_rows = con.execute(
            "SELECT source, dest, type FROM links ORDER BY rowid"
        ).fetchall()

    ids = {decode_lisp_string(row[0]) for row in node_rows}

    tags: defaultdict[str, set[str]] = defaultdict(set)
    for node_id, tag in tag_rows:
        if tag is not None:
            tags[decode_lisp_string(node_id)].add(decode_lisp_string(tag))

    links: defaultdict[str, list[str]] = defaultdict(list)
    misc_links: defaultdict[str, list[OrgLink]] = defaultdict(list)
    for source, dest, link_type in link_rows:
        source = decode_lisp_string(source)
        dest = decode_lisp_string(dest)
        link_type = decode_lisp_string(link_type)
        if link_type == "id":
            if dest in ids:
                links[source].append(dest)
        else:
            misc_links[source].append(OrgLink(link_type, dest, None))

    nodes = {}
    for raw_id, raw_file, raw_title in node_rows:
        node_id = decode_lisp_string(raw_id)
        nodes[node_id] = RoamNode(
            node_id,
            decode_lisp_string(raw_title),
            decode_lisp_string(raw_file),
            tags[node_id],
            [node_id, *links[node_id]],
            misc_links[node_id],
        )
    return nodes


class RoamGraph:
    """Store information of ``org-roam`` graph.

    By default, the nodes in the _node_index are ordered ascending on
    the node IDs. In the documentation, the words "collection", "network",
    "graph", all mean the same thing: the graph with nodes the ``org-roam`` nodes
    and edges determined by backlinks in the ``org-roam`` collection.

    The location of the ``org-roam`` database is the value of ``(org-roam-db-location)``::

      from orgroamtools.data import RoamGraph
      collection = RoamGraph(LOCATION_OF_DB)

    Attributes
    ----------
    db_path : ``str``
        Path to org-roam database connected to graph

    _id_title_map : ``dict[str,str]``
        Map with keys the id of nodes and values the titles of the corresponding nodes
    _graph : ``nx.MultiDiGraph``
        ``networkx`` graph representation of the collection
    _node_index : ``dict[str, RoamNode]``
        Map with keys the ID of nodes and values the ``RoamNode`` object that corresponds
    _orphans : ``list[RoamNode]``
        List of orphans in network. An orphan node is one with no links connecting it to any
        other node
    _is_connected : ``bool``
        Tracks if network is connected (i.e. has no orphans)
    _duplicate_titles : ``list[str]``
        List of duplicated titles in network, used for warning user
    _contains_dup_titles : ``bool``
        Whether the collection has duplicated titles
    """

    def __init__(self, db: str):
        """Initializes RoamGraph object

        The RoamGraph object stores information about the nodes in the
        collection described by the database path provided. The nodes also store
        information about how they relate to each other via backlinks.

        Parameters
        ----------
        db : ``str``
            Path to org-roam database

        Raises
        ------
        FileNotFoundError
            If ``db`` (after ``~`` expansion) is not an existing file.
        sqlite3.DatabaseError
            If the file is not a readable SQLite database.

        Examples
        --------
        >>> collection = RoamGraph(PATH_TO_ORGROAM_DB)
        """

        self.db_path = os.path.expanduser(db)
        if not os.path.isfile(self.db_path):
            raise FileNotFoundError(f"No such file or directory: {self.db_path}")

        self._node_index = _load_nodes(self.db_path)
        self._rebuild(stacklevel=3)

    @classmethod
    def _from_nodes(cls, nodes: Iterable[RoamNode], db_path: str) -> RoamGraph:
        """Build a collection from nodes, as filters do.

        Nodes are copied, and links to nodes not in ``nodes`` are dropped.
        A subset of a collection can't gain duplicate titles, so this doesn't
        repeat the duplicate-title warning.
        """
        graph = cls.__new__(cls)
        graph.db_path = db_path
        graph._node_index = cls._consistent_copy(nodes)
        graph._rebuild(stacklevel=None)
        return graph

    @staticmethod
    def _consistent_copy(nodes: Iterable[RoamNode]) -> dict[str, RoamNode]:
        """Copy nodes, dropping links to IDs that are not among them."""
        nodes = list(nodes)
        ids = {node.id for node in nodes}
        return {
            node.id: replace(
                node,
                tags=set(node.tags),
                backlinks=[link for link in node.backlinks if link in ids],
                misc_links=list(node.misc_links),
            )
            for node in nodes
        }

    def _rebuild(self, stacklevel: int | None = 2) -> None:
        """Derive the graph and indexes from ``_node_index``.

        This is the only place where derived state is computed. ``stacklevel``
        is passed to the duplicate-title warning; ``None`` skips the warning.
        """
        nodes = self._node_index

        self._id_title_map = {node_id: node.title for node_id, node in nodes.items()}

        title_to_ids: defaultdict[str, list[str]] = defaultdict(list)
        for node_id, node in nodes.items():
            title_to_ids[node.title].append(node_id)
        self._title_to_ids = dict(title_to_ids)
        self._duplicate_titles = [
            title for title, ids in self._title_to_ids.items() if len(ids) > 1
        ]
        self._contains_dup_titles = bool(self._duplicate_titles)
        if self._contains_dup_titles and stacklevel is not None:
            warnings.warn(
                "Collection contains duplicate titles. Matching nodes by title will be non-exhaustive.",
                DuplicateTitlesWarning,
                stacklevel=stacklevel,
            )

        graph = nx.MultiDiGraph()
        graph.add_nodes_from(nodes)
        graph.add_edges_from(
            (node_id, link)
            for node_id, node in nodes.items()
            for link in node.backlinks
            if link in nodes
        )
        self._graph = graph

        self._orphans = [
            node
            for node_id, node in nodes.items()
            if not (set(graph.successors(node_id)) | set(graph.predecessors(node_id)))
            - {node_id}
        ]
        self._is_connected = not self._orphans

    def _resolve_title(self, title: str, stacklevel: int = 3) -> RoamNode:
        """Return the first node with ``title``, warning if the title is duplicated."""
        ids = self._title_to_ids.get(title)
        if ids is None:
            raise NodeNotFoundError(f"No node with provided title: {title}")
        if len(ids) > 1:
            warnings.warn(
                "This title is duplicated. This may not be the result you want",
                DuplicateTitlesWarning,
                stacklevel=stacklevel,
            )
        return self._node_index[ids[0]]

    def _resolve(self, identifier: str) -> RoamNode:
        """Return the node with ID ``identifier``, or else the first with that title."""
        node = self._node_index.get(identifier)
        if node is not None:
            return node
        try:
            return self._resolve_title(identifier, stacklevel=4)
        except NodeNotFoundError:
            raise NodeNotFoundError(
                f"No node with provided identifier: {identifier}"
            ) from None

    def remove_orphans(self) -> RoamGraph:
        """Remove orphans from network

        This method returns a new network that has orphans removed.

        Returns
        -------
        RoamGraph
            Connected subcollection of self

        Examples
        --------
        >>> orphanless = collection.remove_orphans()
        >>> print(orphanless._is_connected)
        True

        """
        orphan_ids = {node.id for node in self._orphans}
        return RoamGraph._from_nodes(
            (node for node in self._node_index.values() if node.id not in orphan_ids),
            self.db_path,
        )

    def node_links(self, identifier: str) -> list[str]:
        """Return links for a particular node

        A node's links is the collection of links made in the body of the node desired.
        By convention, a node will always refer to itself

        Parameters
        ----------
        identifier : ``str``
            Identifier for node. Can be title or ID

        Returns
        -------
        ``list[str]``
            List of IDs of nodes the provided node refers to

        Raises
        ------
        ``NodeNotFoundError``
            Raised if identifier cannot be found in the collection
        """
        return self._resolve(identifier).backlinks

    def node(self, identifier: str) -> RoamNode:
        """Return node object

        Internally a node is of class ``orgroamtools.data.RoamNode``, which stores
        basic information about a node like ID, title, filename, and its backlinks

        Parameters
        ----------
        identifier : str
            Identifier for node. Can be title or ID

        Returns
        -------
        ``RoamNode``
            RoamNode object of node

        Raises
        ------
        ``NodeNotFoundError``
            Raised if node cannot be found
        """
        return self._resolve(identifier)

    def node_title(self, identifier: str) -> str:
        """Return title of node

        The title of a node is the name given to the note file.
        If your org-roam node is its own file, this is the #+title: property.
        If you org-roam node is a heading, this is the heading title

        Parameters
        ----------
        identifier : ``str``
            ID of node

        Returns
        -------
        ``str``
            Title of node

        Raises
        ------
        ``NodeNotFoundError``
            Raised if ID not be found in collection
        """
        if identifier not in self._id_title_map:
            raise NodeNotFoundError(f"No node with provided ID: {identifier}")
        return self._id_title_map[identifier]

    def node_id(self, identifier: str) -> str:
        """Return ID of node

        org-roam uses org-mode's internal ``:ID:`` property creation to uniquely identify nodes
        in the collection.

        Parameters
        ----------
        identifier : ``str``
            Title of node

        Returns
        -------
        ``str``
            ID of node

        Raises
        ------
        ``NodeNotFoundError``
            Raised if no node matches the provided title
        """
        return self._resolve_title(identifier).id

    def filter_tags(self, tags: Iterable[str], exclude: bool = True) -> RoamGraph:
        """Filter network by collection of tags

        Parameters
        ----------
        tags : ``Iterable[str]``
            Tags to filter by
        exclude : ``bool``
            If ``True`` (default), drop nodes that have any of ``tags``. If ``False``,
            keep only nodes that have at least one of ``tags``. Surviving nodes keep
            all of their tags, and links to dropped nodes are removed.

        Returns
        -------
        ``RoamGraph``
            Filtered collection (as a copy)

        Examples
        --------
        >>> tags = {"tag1", "tag2"}
        >>> filtered = collection.filter_tags(tags, exclude = True)
        >>> print(tags.issubset(filtered.all_tags()))
        False


        """
        tags = set(tags)
        return RoamGraph._from_nodes(
            (
                node
                for node in self._node_index.values()
                if bool(node.tags & tags) != exclude
            ),
            self.db_path,
        )

    def all_tags(self) -> set[str]:
        """Return collection of all tags present in network

        Returns
        -------
        ``set[str]``
            Set of tags present in network
        """
        return {tag for node in self._node_index.values() for tag in node.tags}

    def refresh(self) -> None:
        """Refresh ``_node_index``-dependent data in collection after
        manual change to ``self._node_index``.

        
        .. deprecated:: 0.2.0
            Assign a new dict to ``node_index`` instead; the collection is
            rebuilt automatically.
        """
        warnings.warn(
            "refresh() is deprecated: assign to node_index instead, which keeps "
            "the collection consistent automatically",
            DeprecationWarning,
            stacklevel=2,
        )
        self._node_index = self._consistent_copy(self._node_index.values())
        self._rebuild(stacklevel=3)

    @property
    def size(self) -> tuple[int, int]:
        """Return size of collection

        Returns
        -------
        ``Tuple[int, int]``
            Tuple (num nodes , num links)
        """
        return (len(self._node_index), nx.number_of_edges(self._graph))

    @property
    def graph(self) -> nx.MultiDiGraph:
        """Return networkx graph representation of collection

        An org-roam collection naturally forms the structure of a
        multi directed graph: a graph with direction-sensitive edges
        allowing multiple edges between any two nodes.

        Returns
        -------
        ``nx.MultiDiGraph``
            Multi directed graph representation of the collection
        """

        return self._graph

    @property
    def backlink_index(self) -> dict[str, list[str]]:
        """Return index for node backlinks of the collection

        When a node in the collection has a reference to another node in the
        collection, it is said to have a backlink to that node. These backlinks
        provide the main nonhierarchical structure of the collection, and compactly
        express relations of different nodes to each other.

        Returns
        -------
        ``dict[str, list[str]]``
            dict with keys the IDs of nodes and values the list of backlinks
            in the node
        """

        return {node.id: node.backlinks for node in self._node_index.values()}

    @property
    def file_index(self) -> dict[str, str]:
        """Return index of filenames of collection

        Returns
        -------
        ``dict[str, str]``
            dict with keys the IDs of nodes and values the filename of the file
            containing that node
        """
        return {ID: node.fname for ID, node in self._node_index.items()}

    @property
    def node_index(self) -> dict[str, RoamNode]:
        """Return index of nodes

        The ``node_index`` is hashed by node ID, since this is the only
        value guaranteed to be unique to each org-roam node across
        various configurations.

        Returns
        -------
        ``dict[str, RoamNode]``
            dict with keys the IDs of nodes and values the RoamNode object
            of the node with that ID
        """
        return self._node_index

    @node_index.setter
    def node_index(self, value: dict[str, RoamNode]) -> None:
        """Set node index

        The graph and all indices are rebuilt. Nodes are copied, and links to IDs
        that are not keys of ``value`` are dropped.

        Parameters
        ----------
            value : ``dict[str,RoamNode]``
                New node index
        """
        self._node_index = self._consistent_copy(value.values())
        self._rebuild(stacklevel=3)

    @property
    def fnames(self) -> list[str]:
        """Return list of filenames in network

        Parameters
        ----------
        base : ``bool``
            get just basename of file

        Returns
        -------
        ``list[str]``
            Path of the file containing each node, in node order.
            Use ``basenames`` for file names only.
        """
        return [node.fname for node in self._node_index.values()]

    @property
    def basenames(self) -> list[str]:
        """Return list of file basenames in network

        Returns
        -------
        ``list[str]``
            list of basenames of the files containing the nodes in network
        """
        return [os.path.basename(node.fname) for node in self._node_index.values()]

    @property
    def nodes(self) -> list[RoamNode]:
        """Return list of nodes in network

        Returns
        -------
        ``list[RoamNode]``
            list of nodes in network
        """
        return list(self._node_index.values())

    @property
    def IDs(self) -> list[str]:
        """Return list of IDs present in network

        Returns
        -------
        ``list[str]``
            list of IDs in network
        """
        return list(self._node_index)

    @property
    def titles(self) -> list[str]:
        """Return list of titles present in network


        Returns
        -------
        ``list[str]``
            list of titles of nodes in network
        """
        return [node.title for node in self._node_index.values()]

    @property
    def misc_link_index(self) -> dict[str, list[OrgLink]]:
        """Return index of miscellaneous links

        Returns
        -------

        dict[str, list[OrgLink]]
            dict with keys IDs of nodes and values the list of backlinks in that
            node that are not links to other nodes (files, URLs, etc.)
        """
        return {ID: node.misc_links for ID, node in self._node_index.items()}

    @property
    def misc_links(self) -> dict[str, list[OrgLink]]:
        """Return list of lists of miscellaneous links

        Returns
        -------
        dict[str, list[str]]
            dict with keys node IDs and values the list of miscellaneous IDs for
            corresponding node
        """
        return {key: node.misc_links for key, node in self._node_index.items()}

    @property
    def id_title_map(self) -> dict[str, str]:
        """Return dictionary of how the network maps IDs to titles

        Returns
        -------
        ``dic[str, str]``
            dict with keys node IDs and values the corresponding title of the
            node

        Examples
        --------
        >>> ids = list(collection.id_title_map.keys())
        >>> ids == collection.IDs
        True
        """
        return self._id_title_map

    @property
    def title_index(self) -> dict[str, str]:
        """Return dictionary of how the network maps IDs to titles

        Synonym for ``id_title_map``.

        Returns
        -------
        ``dic[str, str]``
            dict with keys node IDs and values the corresponding title of the
            node

        Examples
        --------
        FIXME: Add docs.

        """
        return self._id_title_map

    @property
    def tag_index(self) -> dict[str, set[str]]:
        """Return dictionary of IDs and the nodes' tag sets

        Returns
        -------
        ``dic[str, set[str]]``
            dict with keys node IDs and values the set of tags of the node
        """
        return {node.id: node.tags for node in self._node_index.values()}

    @property
    def body_index(self) -> dict[str, str]:
        """Return index of body text for each node.

        Returns
        -------
        ``dict[str, str]``
            Index with value the body text of nodes

        """
        # Group by file so each file is parsed at most once, even if the
        # parse cache is smaller than the number of files
        by_file: defaultdict[str, list[RoamNode]] = defaultdict(list)
        for node in self._node_index.values():
            by_file[node.fname].append(node)
        bodies = {}
        for fname, file_nodes in by_file.items():
            file_bodies = _file_bodies(fname)
            for node in file_nodes:
                bodies[node.id] = _lookup_body(node.id, fname, file_bodies)
        return {node_id: bodies[node_id] for node_id in self._node_index}

    def get_body(self, identifier: str) -> str:
        """Return body of node

        Parameters
        ----------
        identifier : ``str``
            Node identifier. Can be ID or title

        Returns
        -------
        ``str``
            Body text of node

        Raises
        ------
        ``NodeNotFoundError``
            If no node matches identifier
        """
        return self._resolve(identifier).body

    @property
    def math_snippet_index(self) -> dict[str, list[str]]:
        """Return latex snippet index


        Returns
        -------
        ``dict[str, list[str]]``
             Index of LaTeX math snippets (delimiters removed, whitespace
             stripped, in document order)
        """
        return {
            node_id: extract_math_snippets(body)
            for node_id, body in self.body_index.items()
        }

    @property
    def adjacency_list(self) -> list[list[str]]:
        """Return adjacency list of collection

        An adjacency list is a (sometimes) more memory-efficient
        way to store the information of a graph. It stores edges of the
        graph instead of correspondences of nodes in a matrix for example.
        If a node ``a`` has an edge pointing to node ``b``, the pair ``[a,b]``
        will appear in the adjacency list. Keeping with the theme of this
        library, the node identifiers will be used to identify the nodes.
        All nodes will appear in the list, since by convention, an org-roam
        node always links to itself.

        Returns
        -------
        ``list[list[str]]``
            Adjacency list of collection with node IDs to identify nodes
        """
        return [
            [node.id, other]
            for node in self._node_index.values()
            for other in node.backlinks
        ]

    def get_latex_snippets(self, identifier: str) -> list[str]:
        """Return latex snippets of node

        Parameters
        ----------
        identifier : ``str``
            Node identifier. Can be ID or title.

        Returns
        -------
        ``list[str]``
            List of LaTeX snippets in node

        Raises
        ------
        ``NodeNotFoundError``
            If no node matches the identifer
        """
        return extract_math_snippets(self._resolve(identifier).body)

    @property
    def src_block_index(self) -> dict[str, list[tuple[str | None, str]]]:
        """Return index of source blocks of nodes

        Returns
        -------
        ``dict[str, list[tuple[str | None, str]]]``
            Index of source blocks. Source blocks are identified by ``Tuple[LANGUAGE, BLOCK_BODY]``.
            ``LANGUAGE`` is ``None`` for blocks without one

        """
        return {
            node_id: extract_src_blocks(body)
            for node_id, body in self.body_index.items()
        }

    def get_src_blocks(self, identifier: str) -> list[tuple[str | None, str]]:
        """Return source blocks of node

        Parameters
        ----------
        identifier : ``str``
            Node identifier. Can be ID or title.

        Returns
        -------
        ``list[tuple[str | None ,str]]``
            List of source blocks in format (LANGUAGE, BLOCK_BODY); ``LANGUAGE`` is ``None``
            for blocks without one

        Raises
        ------
        ``NodeNotFoundError``
            If no node matches identifier
        """
        return extract_src_blocks(self._resolve(identifier).body)


@dataclass
class OrgLink:
    """
    Store information about org links

    Attributes
    ----------
    type : ``str``
        the type of link (e.g. https, file)
    content : ``str``
        content of the link
    desc : ``Optional[str]``
        description of the link
    """

    type: str
    content: str
    desc: str | None
