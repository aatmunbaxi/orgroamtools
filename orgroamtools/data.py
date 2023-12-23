from __future__ import annotations
import os
import warnings
import sqlite3 as sql
import copy
from typing import Iterable, Tuple, Optional
from dataclasses import dataclass

import networkx as nx

import orgparse as op

from orgroamtools._utils import (
    IdentifierType,
    DuplicateTitlesWarning,
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
        root = op.load(self.fname)
        node_heading = None
        for node in root:
            if node.get_property("ID") == self.id:
                node_heading = node
                break

        return "\n".join(subtree.get_body() for subtree in node_heading)


class RoamGraph:
    """Store information of ``org-roam`` graph.

    By default, the nodes in the _node_index are ordered ascending on
    the node IDs. In the documentation, the words "collection", "network",
    "graph", all mean the same thing: the graph with nodes the ``org-roam`` nodes
    and edges determined by backlinks in the ``org-roam`` collection.

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

    @classmethod
    def init_empty(self):
        """Initialize empty RoamNode object

        Returns
        -------
        RoamNode object with default fields initialized
        """
        self.db_path = None

        self._duplicate_titles = []
        self._contains_dup_titles = None

        self._id_title_map = dict()
        self._graph = None
        self._node_index = dict()

        self._misc_link_index = dict()
        self._orphans = []
        self._is_connected = None
        return self

    def __init__(self, db: str):
        """Initializes RoamGraph object

        The RoamGraph object stores information about the nodes in the
        collection described by the database path provided. The nodes also store
        information about how they relate to each other via backlinks.

        Parameters
        ----------
        db : ``str``
            Path to org-roam database

        Examples
        --------
        >>> collection = RoamGraph(PATH_TO_ORGROAM_DB)
        """

        super(RoamGraph, self).__init__()

        self.db_path = os.path.expanduser(db)
        if not os.path.isfile(self.db_path):
            raise AttributeError(f"No such file or directory: {self.db_path}")

        _fnames = self.__init_fnames(self.db_path)

        _titles = self.__init_titles(self.db_path)
        _ids = self.__init_ids(self.db_path)
        links = self.__init_links_to(db)
        _links_to = [[ID for ID in link_list if ID in _ids] for link_list in links]
        _tags = self.__init_tags(self.db_path)
        _misc_links = self.__init_misc_links(self.db_path)

        self._node_index = {
            j[2]: RoamNode(j[0], j[1], j[2], j[3], j[4], j[5])
            for j in zip(_ids, _titles, _fnames, _tags, _links_to, _misc_links)
        }
        seen = set()
        self._duplicate_titles = [x for x in self.titles if x in seen or seen.add(x)]
        self._contains_dup_titles = len(self._duplicate_titles) > 0
        if self._contains_dup_titles:
            warnings.warn(
                "Collection contains duplicate titles. Matching nodes by title will be non-exhaustive.",
                DuplicateTitlesWarning,
            )

        # In rare cases we'll pick up links to nonexistent nodes
        self._misc_link_index = {_ids[i]: _misc_links[i] for i in range(len(_ids))}

        self._id_title_map = {_ids[i]: self.titles[i] for i in range(len(_ids))}

        self._graph = nx.MultiDiGraph({_ids[i]: _links_to[i] for i in range(len(_ids))})

        self._orphans = [
            node
            for node in self._node_index.values()
            if not any(
                [
                    self._nodes_linked(node, other, directed=False)
                    for other in self._node_index.values()
                    if other != node
                ]
            )
        ]
        self._is_connected = self._orphans == []

    def __filter_tags(self, tags: list[str], exclude: bool) -> list[RoamNode]:
        """Filter network by tags


        Parameters
        ----------
        tags : ``list[str]``
            List of tags to filter by
        exclude : ``bool``
            Whether to exclude the tags in the new network or not
        """
        tfilter = [self._node_has_tag(node, tag) for node in self.nodes for tag in tags]
        if exclude:
            tfilter = [not b for b in tfilter]
        return [node for (node, b) in zip(self.nodes, tfilter) if b]

    def __init_ids(self, dbpath: str) -> list[str]:
        """Initialize list of IDs for each node

        Parameters
        ----------
        dbpath : ``str``
            Path of org-roam database

        Returns
        -------
        List of node IDs
        """
        id_query = "SELECT id FROM nodes ORDER BY id ASC;"
        try:
            with sql.connect(dbpath, uri=True) as con:
                csr = con.cursor()
                query = csr.execute(id_query)
                return [i[0].replace('"', "") for i in query.fetchall()]

        except sql.Error as e:
            print("Connection failed: ", e)
        return []

    def __init_fnames(self, dbpath: str) -> list[str]:
        """
        Initializes list of filenames for each node

        Parameters
        ----------
        dbpath : ``str``
            Path to org-roam database

        Returns
        -------
        List of node filepaths
        """
        fname_query = "SELECT file FROM nodes ORDER BY id ASC;"
        try:
            with sql.connect(dbpath, uri=True) as con:
                csr = con.cursor()
                query = csr.execute(fname_query)
                return [i[0].replace('"', "") for i in query.fetchall()]

        except sql.Error as e:
            print("Connection failed: ", e)
        return []

    def __init_titles(self, dbpath: str) -> list[str]:
        """
        Initialize list of titles for each node

        Parameters
        ----------
        dbpath : ``str``
               Path to org-roam database


        Returns
        -------
        List of node titles
        """
        title_query = "SELECT title FROM nodes ORDER BY id ASC;"
        try:
            with sql.connect(dbpath, uri=True) as con:
                csr = con.cursor()
                query = csr.execute(title_query)
                return [i[0].replace('"', "") for i in query.fetchall()]

        except sql.Error as e:
            print("Connection failed: ", e)
        return []

    def __init_tags(self, dbpath: str) -> list[set[str]]:
        """
        Initialize list of tags for each node

        Parameters
        ----------
        dbpath : ``str``
                Path to org-roam database

        Returns
        -------
        List of node tags (as sets)
        """
        tags_query = "SELECT nodes.id, GROUP_CONCAT(tags.tag) AS tags FROM nodes LEFT JOIN tags ON nodes.id = tags.node_id GROUP BY nodes.id ORDER BY nodes.id ASC;"
        try:
            with sql.connect(dbpath, uri=True) as con:
                csr = con.cursor()
                query = csr.execute(tags_query)
                clean = lambda s: s.replace('"', "")
                match_null = lambda s: set() if not s else s.split(",")
                return [set(map(clean, match_null(i[1]))) for i in query.fetchall()]

        except sql.Error as e:
            print("Connection failed: ", e)
        return []

    def __init_links_to(self, dbpath: str) -> list[list[str]]:
        """Initialize list of links

        Parameters
        ----------
        dbpath : ``str``
               Path to org-roam database


        Returns
        -------
        List of backlinks in node (as a list)
        """
        links_to_query = """
        SELECT n.id,
        GROUP_CONCAT(CASE WHEN l.type = '"id"' THEN l.dest END)
        FROM nodes n
        LEFT JOIN links l ON n.id = l.source
        GROUP BY n.id
        ORDER BY n.id ;
        """
        try:
            with sql.connect(dbpath, uri=True) as con:
                csr = con.cursor()
                query = csr.execute(links_to_query)
                clean = lambda s: s.replace('"', "")
                links = query.fetchall()

                # Separated links by comma might still have links we dont want (e.g. files, etc)
                self_and_links = [
                    [clean(i[0])] + list(map(clean, i[1].split(",")))
                    if i[1]
                    else [clean(i[0])]
                    for i in links
                ]

                return self_and_links

        except sql.Error as e:
            print("Connection failed: ", e)
        return []

    def __init_misc_links(self, dbpath: str) -> list[list[OrgLink]]:
        """Initialize list of miscellaneous org-mode links

        Parameters
        ----------
        dbpath : ``str``
            path to org-roam database

        Returns
        -------
        ``list[OrgLink]``
            List of OrgRoam links that are not other nodes (files, images,
            internet links, etc)

        Examples
        --------
        FIXME: Add docs.

        """
        q = """SELECT n.id, GROUP_CONCAT(CASE WHEN l.type != '"id"' THEN l.dest END),
                GROUP_CONCAT(CASE WHEN l.type != '"id"' THEN l.type END)
                FROM
                    nodes n
                LEFT JOIN
                    links l ON n.id = l.source
                GROUP BY
                    n.id
                ORDER BY
                    n.id;"""
        try:
            with sql.connect(dbpath, uri=True) as con:
                csr = con.cursor()
                clean = lambda s: s.replace('"', "")
                quer = csr.execute(q)
                output = quer.fetchall()
                links_and_types = [
                    list(
                        zip(
                            tuple(clean(row[1]).split(",")),
                            tuple(clean(row[2]).split(",")),
                        )
                    )
                    if row[1]
                    else []
                    for row in output
                ]
                return [
                    [OrgLink(prop[1], prop[0], None) if prop else [] for prop in lst]
                    for lst in links_and_types
                ]

        except sql.Error as e:
            print("Connection failed: ", e)
        return []

    def remove_orphans(self) -> RoamGraph:
        """Remove orphans from network

        This method returns a new network that has orphans removed.

        Returns
        -------
        RoamGraph
            Connected subcollection of self
        Examples
        --------
        FIXME: Add docs.

        """
        indices_of_orphans = [
            i for i in range(len(self.IDs)) if self.nodes[i] in self._orphans
        ]

        new_node_data = [
            data
            for idx, data in enumerate(
                zip(
                    self.fnames,
                    self.titles,
                    self.IDs,
                    self._tags,
                    self._links_to,
                    self.misc_links.values(),
                )
            )
            if idx not in indices_of_orphans
        ]
        new_node_index = {
            j[2]: RoamNode(j[0], j[1], j[2], j[3], j[4], j[5]) for j in new_node_data
        }
        # _fnames = [j[0] for j in new_node_data]
        # _titles = [j[1] for j in new_node_data]
        # _ids = [j[2] for j in new_node_data]
        # _tags = [j[3] for j in new_node_data]
        # _links_to = [j[4] for j in new_node_data]
        self._node_index = new_node_index
        # Should be true by definition...
        self._orphans = []
        self._is_connected = True

        self.db_path = self.db_path
        self._graph = nx.MultiDiGraph(
            {self.IDs[i]: self._links_to[i] for i in range(len(self.IDs))}
        )
        self._id_title_map = {self.IDs[i]: self.titles[i] for i in range(len(self.IDs))}
        return self

    def __is_orphan(self, node: RoamNode) -> bool:
        """Check if node is an orphan

        Parameters
        ----------
        node : ``RoamNode``
            Node to check

        Returns
        -------
        ``bool``
            True if node is an orphan

        Examples
        --------
        FIXME: Add docs.

        """
        pointed_to = True if any(node.id in n.backlinks for n in self.nodes) else False
        points_to = node.backlinks != []
        return not points_to and not pointed_to

    def _identifier_type(self, identifier: str) -> IdentifierType:
        """Determine type of identifier for node

        Parameters
        ----------
        identifier : ``str``
            identifier; node ID or title

        Returns
        -------
        ``IdentifierType``
            Type of identifier

        Examples
        --------
        FIXME: Add docs.

        """
        if identifier in self.IDs:
            return IdentifierType.ID
        elif identifier in self.titles:
            if identifier in self._duplicate_titles:
                warnings.warn(
                    "This title is duplicated. This may not be the result you want",
                    DuplicateTitlesWarning,
                )
            return IdentifierType.TITLE
        else:
            return IdentifierType.NOTHING

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
        ``AttributeError``
            Raised if identifier cannot be found in the collection
        """

        identifier_type = self._identifier_type(identifier)

        match identifier_type:
            case IdentifierType.ID:
                return self._node_index[identifier].backlinks

            case IdentifierType.TITLE:
                idx = self.titles.index(identifier)
                return self.nodes[idx].backlinks

            case IdentifierType.NOTHING:
                raise AttributeError(f"No node with identifier: {identifier}")

    def node(self, identifier: str) -> RoamNode:
        """Return node object

        Internally a node is of class orgroamtools.data.RoamNode, which stores
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
        ``AttributeError``
            Raised if node cannot be found
        """
        identifier_type = self._identifier_type(identifier)

        match identifier_type:
            case IdentifierType.TITLE:
                idx = self.titles.index(identifier)
                return self.nodes[idx]

            case IdentifierType.ID:
                idx = self.titles.index(identifier)
                return self.nodes[idx]

            case IdentifierType.NOTHING:
                raise AttributeError(f"No node with provided identifier: {identifier}")

        raise AttributeError("Uh oh spaghetti-o")

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
        ``AttributeError``
            Raised if ID not be found in collection
        """
        identifier_type = self._identifier_type(identifier)

        match identifier_type:
            case IdentifierType.ID:
                return self._id_title_map[identifier]

        raise AttributeError(f"No node with provided ID: {identifier}")

    def node_id(self, identifier: str) -> str:
        """Return ID of node

        org-roam uses org-mode's internal :ID: property creation to uniquely identify nodes
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
        ``AttributeError``
            Raised if no node matches the provided title
        """

        identifier_type = self._identifier_type(identifier)

        match identifier_type:
            case IdentifierType.TITLE:
                index_of_id = self.titles.index(identifier)
                return self.IDs[index_of_id]

        raise AttributeError(f"No node with provided title: {identifier}")

    def filter_tags(self, tags: Iterable[str], exclude: bool = True) -> RoamGraph:
        """Filter network by collection of tags

        Parameters
        ----------
        tags : ``Iterable[str]``
            Tags to filter by
        exclude : ``bool``
            To exclude or not

        Returns
        -------
        ``RoamGraph``
            Filtered collection (as a copy)

        Examples
        --------
        FIXME: Add docs.

        """

        subgraph = copy.deepcopy(self)

        new_nodes, excluded_ids = subgraph.__partitioned_nodes(tags, exclude)

        _ids = [node.id for node in new_nodes]
        _titles = [node.title for node in new_nodes]
        _fnames = [node.fname for node in new_nodes]

        # A node now cannot link to an excluded node, so excise them
        _links_to = [
            [link for link in node.backlinks if link not in excluded_ids]
            for node in new_nodes
        ]
        subgraph._graph = nx.MultiDiGraph(
            {_ids[i]: _links_to[i] for i in range(len(_titles))}
        )

        seen = set()
        subgraph._duplicate_titles = [x for x in _titles if x in seen or seen.add(x)]
        subgraph._contains_dup_titles = len(subgraph._duplicate_titles) > 0
        if subgraph._contains_dup_titles:
            warnings.warn(
                "Collection contains duplicate titles. Matching nodes by title will be non-exhaustive.",
                DuplicateTitlesWarning,
            )

        subgraph._id_title_map = {_ids[i]: _titles[i] for i in range(len(_ids))}

        remove_tags = lambda taglist: list(set(taglist) - set(tags))
        subgraph._node_index = {
            j[2]: RoamNode(j[0], j[1], j[2], j[3], j[4], j[5])
            for j in zip(
                _fnames,
                _titles,
                _ids,
                list(map(remove_tags, self._tags)),
                _links_to,
                self.misc_links.values(),
            )
        }

        subgraph._orphans = [
            node
            for node in subgraph._node_index.values()
            if not any(
                [
                    self._nodes_linked(node, other)
                    for other in subgraph._node_index.values()
                ]
            )
        ]

        subgraph._is_connected = subgraph._orphans == []
        return subgraph

    def _nodes_linked(
        self, node1: RoamNode, node2: RoamNode, directed: bool = True
    ) -> bool:
        """Determine if two nodes are linked

        Parameters
        ----------
        node1 : ``RoamNode``
            Origin node
        node2 : ``RoamNode``
            Destination node
        directed : ``bool``
            Do comparison directed

        Returns
        -------
            True if nodes are connected
        Examples
        --------
        FIXME: Add docs.

        """
        if directed:
            return node2.id in node1.backlinks
        else:
            return node2.id in node1.backlinks or node1.id in node2.backlinks

    def all_tags(self) -> set[str]:
        """Return collection of all tags present in network

        Returns
        -------
        ``set[str]``
            Set of tags present in network

        Examples
        --------
        FIXME: Add docs.

        """
        return set(tag for node in self._node_index.values() for tag in node.tags)

    def __partitioned_nodes(
        self, tags: Iterable[str], exclude: bool = True
    ) -> Tuple[list[RoamNode], list[str]]:
        """Filter network by exact matches on tags

        Parameters
        ----------
        tags : ``Iterable[str]``
            Tags
        exclude : ``bool``
            Whether to exclude in new network or not

        Returns
        -------
        ``Tuple[list[RoamNode], list[str]]``
            Tuple containing list of nodes that survive filtering and list of IDs
            that were purged

        Examples
        --------
        FIXME: Add docs.

        """
        tfilter = [
            any([tag in node.tags for tag in tags])
            for node in self._node_index.values()
        ]
        if exclude:
            tfilter = [not b for b in tfilter]
            excluded_tags = tags
            excluded_ids = [
                node.id
                for node in self._node_index.values()
                if any(tag in node.tags for tag in excluded_tags)
            ]
        elif not exclude:
            excluded_tags = self._all_tags() - set(tags)
            excluded_ids = [
                node.id
                for node in self._node_index.values()
                if not any(tag in node.tags for tag in excluded_tags)
            ]

        return ([node for (node, b) in zip(self.nodes, tfilter) if b], excluded_ids)

    def _node_has_tag(self, node: RoamNode, tag: str) -> bool:
        """
        Return if node has provided tag

        Parameters
        ----------
        node : ``RoamNode``
            Node to check
        tag : ``str``
            Tag to check

        Returns
        -------
        bool
            True if ``node`` has ``tag``
        """
        return tag in node.tags

    def refresh(self) -> None:
        """Refresh ``_node_index``-dependent data in collection after
        manual change to ``self._node_index``.
        """
        seen = set()
        self._duplicate_titles = [x for x in self.titles if x in seen or seen.add(x)]
        self._contains_dup_titles = len(self._duplicate_titles) > 0
        if self._contains_dup_titles:
            warnings.warn(
                "Collection contains duplicate titles. Matching nodes by title will be non-exhaustive.",
                DuplicateTitlesWarning,
            )

        self._id_title_map = {self.IDs[i]: self.titles[i] for i in range(len(self.IDs))}

        self._graph = nx.MultiDiGraph(
            {self.IDs[i]: self.backlink_index[i] for i in range(len(self.IDs))}
        )

        self._orphans = [
            node
            for node in self._node_index.values()
            if not any(
                [
                    self._nodes_linked(node, other, directed=False)
                    for other in self._node_index.values()
                    if other != node
                ]
            )
        ]
        self._is_connected = self._orphans == []

    @property
    def size(self) -> Tuple[int, int]:
        """Return size of collection

        Returns
        -------
        ``Tuple[int, int]``
            Tuple (num nodes , num links)
        """
        return (len(self._node_index), nx.number_of_edges(self._graph))

    @property
    def _tags(self) -> list[set[str]]:
        """Return list of tag collections of nodes

        Returns
        -------
        ``list[set[str]]``
            List of sets containing tags of nodes

        Examples
        --------
        FIXME: Add docs.

        """
        return [node.tags for node in self._node_index.values()]

    @property
    def _links_to(self) -> list[list[str]]:
        """Return list lists of node backlinks

        Returns
        -------
        ``list[list[str]]``
            List of backlinks for nodes

        Examples
        --------
        FIXME: Add docs.

        """
        return [node.backlinks for node in self._node_index.values()]

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

        Examples
        --------
        FIXME: Add docs.
        """

        return self._graph

    @graph.setter
    def graph(self, value: nx.MultiDiGraph) -> None:
        """Setter for graph attribute

        Parameters
        ----------
        value : ``nx.MultiDiGraph``
            new graph to set self._graph to

        Examples
        --------
        FIXME: Add docs.

        """

        self._graph = value

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

        Examples
        --------
        FIXME: Add docs.
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

        Examples
        --------
        FIXME: Add docs.

        """
        return {ID: node.fname for ID, node in self._node_index.items()}

    @property
    def node_index(self) -> dict[str, RoamNode]:
        """Return index of nodes

        The node_index is hashed by node ID, since this is the only
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
        """Set for node index

        Parameters
        ----------
        value : ``dict[str,RoamNode]``
            New node index
        """
        self._node_index = value

    @property
    def fnames(self, base: bool = True) -> list[str]:
        """Return list of filenames in network

        Parameters
        ----------
        base : ``bool``
            get just basename of file

        Returns
        -------
        ``list[str]``
            list of filenames in network

        Examples
        --------
        FIXME: Add docs.

        """
        if base:
            return [os.path.basename(node.fname) for node in self.node_index.values()]

        return [node.fname for node in self.nodes]

    @property
    def nodes(self) -> list[RoamNode]:
        """Return list of nodes in network

        Returns
        -------
        ``list[RoamNode]``
            list of nodes in network

        Examples
        --------
        FIXME: Add docs.

        """
        return list(self.node_index.values())

    @property
    def IDs(self) -> list[str]:
        """Return list of IDs present in network

        Returns
        -------
        ``list[str]``
            list of IDs in network

        Examples
        --------
        FIXME: Add docs.

        """
        return [node.id for node in self.node_index.values()]

    @property
    def titles(self) -> list[str]:
        """Return list of titles present in network


        Returns
        -------
        ``list[str]``
            list of titles of nodes in network

        Examples
        --------
        FIXME: Add docs.

        """
        return [node.title for node in self._node_index.values()]

    @property
    def links(self) -> dict[str, list[str]]:
        """Return dict of node IDs and their backlinks

        Returns
        -------
        ``dict[str, list[str]]``
            dict with keys IDs of nodes and values the list of backlinks in that
            node

        Examples
        --------
        FIXME: Add docs.

        """
        return {ID: node.backlinks for ID, node in self._node_index.items()}

    @property
    def misc_link_index(self) -> dict[str, list[OrgLink]]:
        """Return index of miscellaneous links

        Returns
        -------
        ``dict[str, list[str]]``
            dict with keys node IDs and values the list of miscellaneous IDs for
            corresponding node

        Examples
        --------
        FIXME: Add docs.

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
        FIXME: Add docs.

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

        Synonym for ``id_title_map``.

        Returns
        -------
        ``dic[str, set[str]]``
            dict with keys node IDs and values the set of tags of the node
        """
        return {node.id: node.tags for node in self.nodes}

    @property
    def body_index(self) -> dict[str, str]:
        """Return index of body text for each node. Note: only implemented
        for collections with one node per file.

        Returns
        -------
        ``dict[str, str]``
            Index with value the body text of nodes

        """
        return {node.id: node.body for node in self.nodes}

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
        ``AttributeError``
            If no node matches identifier
        """
        id_type = self._identifier_type(identifier)
        match id_type:
            case IdentifierType.TITLE:
                idx = self.titles.index(identifier)
                return self.nodes[idx].body
            case IdentifierType.ID:
                return self._node_index[identifier].body
            case IdentifierType.NOTHING:
                raise AttributeError(f"No node with provided identifier: {identifier}")

    @property
    def math_snippet_index(self) -> dict[str, list[str]]:
        """Return latex snippet index


        Returns
        -------
        ``dict[str, list[str]]``
            Index of LaTeX snippets
        """
        return {node.id: extract_math_snippets(node.body) for node in self.nodes}

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
        ``AttributeError``
            If no node matches the identifer
        """
        id_type = self._identifier_type(identifier)
        match id_type:
            case IdentifierType.ID:
                return extract_math_snippets(self._node_index[identifier].body)
            case IdentifierType.TITLE:
                idx = self.titles.index(identifier)
                return extract_math_snippets(self.nodes[idx].body)
            case IdentifierType.NOTHING:
                raise AttributeError(f"No node with identifier: {identifier}")

    @property
    def src_block_index(self) -> dict[str, list[str]]:
        """Return source blocks of node

        Returns
        -------
        ``dict[str, list[Tuple[str,str]]]``
            Index of source blocks. Source blocks are identified by ``Tuple[LANGUAGE, BLOCK_BODY]``

        """
        return {node.id: extract_src_blocks(node.body) for node in self.nodes}

    def get_src_blocks(self, identifier: str) -> list[Tuple[str, str]]:
        """Return source blocks of node

        Parameters
        ----------
        identifier : ``str``
            Node identifier. Can be ID or title.

        Returns
        -------
        ``list[Tuple[str,str]]``
            List of source blocks in format (LANGUAGE, BLOCK_BODY)

        Raises
        ------
        ``AttributeError``
            If no node matches identifier
        """
        id_type = self._identifier_type(identifier)
        match id_type:
            case IdentifierType.ID:
                return extract_src_blocks(self._node_index[identifier].body)
            case IdentifierType.TITLE:
                idx = self.titles.index(identifier)
                return extract_src_blocks(self.nodes[idx].body)
            case IdentifierType.NOTHING:
                raise AttributeError(f"No node with identifier: {identifier}")


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
    desc: Optional[str]
