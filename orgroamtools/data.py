import os
import re
import warnings
import sqlite3 as sql
import copy
from typing import Iterable, Tuple
from dataclasses import dataclass

import networkx as nx

from orgroamtools._utils import (
    IdentifierType,
    DuplicateTitlesWarning,
    ORG_ID_FORMAT,
    MiscLink,
    parse_orglink
)


@dataclass
class RoamNode:
    """Store relevant org-roam node information

    Parameters
    ----------
    fname : str
        Filename of org-roam node
    title : str
        Title of org-roam node
    id : str
        Unique org ID of org-roam node
    tags : set[str]
        Collection of tags of org-roam node
    links : list[str]
        List of backlinks in org-roam node
    misc_links : list[MiscLink]
        List of miscellaneous links that are not links to other nodes
    """

    fname: str
    title: str
    id: str
    tags: set[str]
    backlinks: list[str]
    misc_links : list[MiscLink]




class RoamGraph:
    """Object to store data associated to a collection of org-roam nodes"""

    @classmethod
    def init_empty(self):
        """Initialize empty RoamNode object

        Returns
        -------
        RoamNode object with default fields initialized
        """
        self.db_path = None
        self._fnames = []
        self._titles = []

        self._duplicate_titles = []
        self._contains_dup_titles = None
        self._ids = []
        self._links_to = []

        self._tags = []

        self._id_title_map = dict()
        self._graph = None
        self._node_index = dict()

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
        db : str
            Path to org-roam database

        Examples
        --------
        >>> collection = RoamGraph(PATH_TO_ORGROAM_DB)
        """

        super(RoamGraph, self).__init__()

        self.db_path = os.path.expanduser(db)
        if not os.path.isfile(self.db_path):
            raise AttributeError(f"No such file or directory: {self.db_path}")

        self._fnames = self.__init_fnames(self.db_path)
        self._titles = self.__init_titles(self.db_path)

        seen = set()
        self._duplicate_titles = [x for x in self._titles if x in seen or seen.add(x)]
        self._contains_dup_titles = len(self._duplicate_titles) > 0
        if self._contains_dup_titles:
            warnings.warn(
                "Collection contains duplicate titles. Matching nodes by title will be non-exhaustive.",
                DuplicateTitlesWarning,
            )

        self._ids = self.__init_ids(self.db_path)
        # In rare cases we'll pick up links to nonexistent nodes
        links = self.__init_links_to(db)
        self._links_to = [
            [ID for ID in link_list if ID in self._ids] for link_list in links
        ]
        self._misc_links = self.__init_misc_links(self.db_path)
        self._misc_link_index = {self._ids[i] : self._misc_links[i] for i in range(len(self._ids))}

        self._tags = self.__init_tags(self.db_path)

        self._id_title_map = {
            self._ids[i]: self._titles[i] for i in range(len(self._ids))
        }

        self._graph = nx.MultiDiGraph(
            {self._ids[i]: self._links_to[i] for i in range(len(self._titles))}
        )
        self._node_index = {
            j[2]: RoamNode(j[0], j[1], j[2], j[3], j[4], j[5])
            for j in zip(
                    self._fnames, self._titles, self._ids, self._tags, self._links_to, self._misc_links
            )
        }

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
    def graph(self) -> nx.MultiDiGraph:
        """Return networkx graph representation of collection

        An org-roam collection naturally forms the structure of a
        multi directed graph: a graph with direction-sensitive edges
        allowing multiple edges between any two nodes.

        Returns
        -------
        nx.MultiDiGraph
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
        value : nx.MultiDiGraph
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
        dict[str, list[str]]
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
        dict[str, str]
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
        dict[str, RoamNode]
            dict with keys the IDs of nodes and values the RoamNode object
            of the node with that ID
        """
        return self._node_index

    @node_index.setter
    def node_index(self, value: dict[str, RoamNode]) -> None:
        """Set for node index

        Parameters
        ----------
        value : dict[str,RoamNode]
            New node index
        """
        self._node_index = value

    def __filter_tags(self, tags: list[str], exclude: bool) -> list[RoamNode]:
        """Filter network by tags


        Parameters
        ----------
        tags : list[str]
            List of tags to filter by
        exclude : bool
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
        dbpath : str
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
        dbpath : str
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
        dbpath : str
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
        dbpath : str
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

    def __init_misc_links(self, dbpath: str) -> list[MiscLink]:
        links_to_query = "SELECT n.id ,GROUP_CONCAT(l.dest), l.type FROM nodes n LEFT JOIN links l ON n.id = l.source GROUP BY n.id ORDER BY n.id ;"
        # If only sqlite supported regexp..
        # links_to_query = "SELECT n.id, GROUP_CONCAT(l.dest ) FROM nodes n LEFT JOIN links l\nON n.id = l.source AND l.dest REGEXP \'^\"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}\"$\'\nGROUP BY n.id\nORDER BY n.id;"
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

                # By default links to files and other things are included in the database
                # so just get rid of them
                return [
                    [link for link in node_links if not re.match(ORG_ID_FORMAT, link)]
                    for node_links in self_and_links
                ]

        except sql.Error as e:
            print("Connection failed: ", e)
        return []


    def __init_links_to(self, dbpath: str) -> list[list[str]]:
        """Initialize list of links

        Parameters
        ----------
        dbpath : str
               Path to org-roam database


        Returns
        -------
        List of backlinks in node (as a list)
        """
        links_to_query = "SELECT n.id, GROUP_CONCAT(l.dest) FROM nodes n LEFT JOIN links l ON n.id = l.source GROUP BY n.id ORDER BY n.id ;"
        # If only sqlite supported regexp..
        # links_to_query = "SELECT n.id, GROUP_CONCAT(l.dest ) FROM nodes n LEFT JOIN links l\nON n.id = l.source AND l.dest REGEXP \'^\"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}\"$\'\nGROUP BY n.id\nORDER BY n.id;"
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

                # By default links to files and other things are included in the database
                # so just get rid of them
                return [
                    [link for link in node_links if re.match(ORG_ID_FORMAT, link)]
                    for node_links in self_and_links
                ]

        except sql.Error as e:
            print("Connection failed: ", e)
        return []

    def remove_orphans(self):
        """Remove orphan nodes

        Orphanless RoamGraph (not done in-place)
        """
        indices_of_orphans = [
            i for i in range(len(self._ids)) if self.nodes[i] in self._orphans
        ]

        new_node_data = [
            data
            for idx, data in enumerate(
                zip(self._fnames, self._titles, self._ids, self._tags, self._links_to)
            )
            if idx not in indices_of_orphans
        ]
        new_node_index = {
            j[2]: RoamNode(j[0], j[1], j[2], j[3], j[4]) for j in new_node_data
        }
        self._fnames = [j[0] for j in new_node_data]
        self._titles = [j[1] for j in new_node_data]
        self._ids = [j[2] for j in new_node_data]
        self._tags = [j[3] for j in new_node_data]
        self._links_to = [j[4] for j in new_node_data]
        self._node_index = new_node_index
        # Should be true by definition...
        self._orphans = []
        self._is_connected = True

        self.db_path = self.db_path
        self._graph = nx.MultiDiGraph(
            {self._ids[i]: self._links_to[i] for i in range(len(self._ids))}
        )
        self._id_title_map = {
            self._ids[i]: self._titles[i] for i in range(len(self._ids))
        }
        return self

    @property
    def fnames(self, base: bool = True) -> list[str]:
        """
        Get list of filenames of graph

        base -- bool (True)
              basenames of files

        Returns list of filenames
        """
        if base:
            return [os.path.basename(node.fname) for node in self.node_index.values()]

        return [node.fname for node in self.nodes]

    @property
    def nodes(self) -> list[RoamNode]:
        """
        Returns list of nodes
        """
        return list(self.node_index.values())

    @property
    def IDs(self) -> list[str]:
        """
        Returns list of node IDs
        """
        return [node.id for node in self.node_index.values()]

    @property
    def titles(self):
        """
        Returns list of node names (#+title file property)
        """
        return self._titles

    @property
    def links(self):
        """
        Returns tuples of (title, links) for each node
        """
        links = [a.backlinks for a in self.nodes]
        return [(a, b) for (a, b) in zip(self.titles, links)]

    def __is_orphan(self, node: RoamNode) -> bool:
        """
        Checks if node is an orphan with respect to others

        Params:
        node -- node to check orphanhood

        Returns True if node is orphan of self
        """
        pointed_to = True if any(node.id in n.backlinks for n in self.nodes) else False
        points_to = node.backlinks != []
        return not points_to and not pointed_to

    def _identifier_type(self, identifier: str) -> IdentifierType:
        """
        Determines type of identifier
        """
        if identifier in self.IDs:
            return IdentifierType.ID
        elif identifier in self.titles:
            return IdentifierType.TITLE
        else:
            return IdentifierType.NOTHING

    def node_links(self, identifier: str) -> list[str]:
        """Return links for a particular node

        A node's links is the collection of links made in the body of the node desired.
        By convention, a node will always refer to itself

        Parameters
        ----------
        identifier : str
            Identifier for node. Can be title or ID

        Returns
        -------
        list[str]
            List of IDs of nodes the provided node refers to

        Raises
        ------
        AttributeError
            Raised if identifier cannot be found in the collection
        """

        identifier_type = self._identifier_type(identifier)

        match identifier_type:
            case IdentifierType.ID:
                return self._node_index[identifier].backlinks

            case IdentifierType.TITLE:
                if identifier in self._duplicate_titles:
                    warnings.warn(
                        "Title is a duplicate. This might not be the desired result.",
                        DuplicateTitlesWarning,
                    )
                idx = self.IDs.index(identifier)
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
        RoamNode
            RoamNode object of node

        Raises
        ------
        AttributeError
            Raised if node cannot be found
        """
        identifier_type = self._identifier_type(identifier)

        match identifier_type:
            case IdentifierType.TITLE:
                if identifier in self._duplicate_titles:
                    warnings.warn(
                        "This title is duplicated. This may not be the node you want",
                        DuplicateTitlesWarning,
                    )
                idx = self.titles.index(identifier)
                return self.nodes[idx]

            case IdentifierType.ID:
                idx = self._ids.index(identifier)
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
        identifier : str
            ID of node

        Returns
        -------
        str
            Title of node

        Raises
        ------
        AttributeError
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
        identifier : str
            Title of node

        Returns
        -------
        str
            ID of node

        Raises
        ------
        AttributeError
            Raised if no node matches the provided title
        """

        identifier_type = self._identifier_type(identifier)
        print(identifier_type)

        match identifier_type:
            case IdentifierType.TITLE:
                if identifier_type in self._duplicate_titles:
                    warnings.warn(
                        "This title is duplicated. This may not be the ID you want.",
                        DuplicateTitlesWarning,
                    )
                index_of_id = self._titles.index(identifier)
                return self.IDs[index_of_id]

        raise AttributeError(f"No node with provided title: {identifier}")

    def filter_tags(self, tags, exclude=True):
        subgraph = copy.deepcopy(self)

        (new_nodes, excluded_ids) = subgraph.__partitioned_nodes(tags, exclude)

        subgraph._ids = [node.id for node in new_nodes]
        subgraph._titles = [node.title for node in new_nodes]
        subgraph._fnames = [node.fname for node in new_nodes]

        # A node now cannot link to an excluded node, so excise them
        subgraph._links_to = [
            [link for link in node.links if link not in excluded_ids]
            for node in new_nodes
        ]
        subgraph._graph = nx.MultiDiGraph(
            {
                subgraph._ids[i]: subgraph._links_to[i]
                for i in range(len(subgraph._titles))
            }
        )

        seen = set()
        subgraph._duplicate_titles = [
            x for x in subgraph._titles if x in seen or seen.add(x)
        ]
        subgraph._contains_dup_titles = len(subgraph._duplicate_titles) > 0
        if subgraph._contains_dup_titles:
            warnings.warn(
                "Collection contains duplicate titles. Matching nodes by title will be non-exhaustive.",
                DuplicateTitlesWarning,
            )

        subgraph._id_title_map = {
            subgraph._ids[i]: subgraph._titles[i] for i in range(len(subgraph._ids))
        }

        subgraph._node_index = {
            j[2]: RoamNode(j[0], j[1], j[2], j[3], j[4])
            for j in zip(
                subgraph._fnames,
                subgraph._titles,
                subgraph._ids,
                subgraph._tags,
                subgraph._links_to,
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

    def _nodes_linked(self, node1: RoamNode, node2: RoamNode, directed: bool = True):
        if directed:
            return node2.id in node1.backlinks
        else:
            return node2.id in node1.backlinks or node1.id in node2.backlinks

    def _all_tags(self) -> set[str]:
        """Get all tags present in the collection"""
        return set(tag for node in self._node_index.values() for tag in node.tags)

    def __partitioned_nodes(
        self, tags: Iterable[str], exclude: bool = True
    ) -> Tuple[list[RoamNode], list[str]]:
        """Filter network by exact matches on tags

        Parameters
        ----------
        tags : Iterable[str]
            Iterable of tags
        exclude : bool
            Whether to exclude in new network or not

        Returns
        -------
        list[RoamNode]
            List of filtered nodes

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
        return tag in node.tags

    # FIXME
    def __filter_rx_tags(self, tags: Iterable[str], exclude: bool) -> list[RoamNode]:
        """Filter network by regex searches on tags

        Parameters
        ----------
        tags : Iterable[str]
            Iterable of regex strings
        exclude : bool
            To exclude the matched tags or not

        Examples
        --------
        FIXME: Add docs.
        """
        # tags = set(map(re.compile, tags))

        # # tfilter = [node.has_regex_tag(tags) for node in self.nodes]
        # tfilter = [
        #     any([rx.match(tag) for tag in node.tags])
        #     for node in self._node_index.values()
        #     for rx in tags
        # ]
        # if exclude:
        #     tfilter = [not b for b in tfilter]
        # return [node for (node, b) in zip(self.nodes, tfilter) if b]

    @property
    def size(self) -> Tuple[int, int]:
        """Return size of collection

        Returns
        -------
        Tuple (num nodes , num links)
        """
        return (len(self._node_index), nx.number_of_edges(self._graph))
