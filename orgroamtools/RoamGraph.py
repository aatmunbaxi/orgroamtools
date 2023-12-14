import os
import warnings
import sqlite3 as sql
import copy

import networkx as nx

from orgroamtools.RoamNode import RoamNode as Node
from orgroamtools._RoamGraphHelpers import IdentifierType, DuplicateTitlesWarning


class RoamGraph:
    """
    Stores information of an org-roam network.
    """

    def __init__(self, db : str):
        """
        Constructor for RoamGraph

        Params
        db -- path to org-roam db (required)
        """

        super(RoamGraph, self).__init__()

        self.db_path = os.path.expanduser(db)

        self._fnames = self.__init_fnames(self.db_path)
        self._titles = self.__init_titles(self.db_path)

        seen = set()
        self._duplicate_titles = [x for x in self._titles if x in seen or seen.add(x)]
        self._contains_dup_titles = len(self._duplicate_titles) > 0
        if self._contains_dup_titles:
            warnings.warn("Collection contains duplicate titles. Matching nodes by title will be non-exhaustive.",
                          DuplicateTitlesWarning)

        self._ids = self.__init_ids(self.db_path)
        self._tags = self.__init_tags(self.db_path)
        self._links_to = self.__init_links_to(self.db_path)

        self._id_title_map = { self._ids[i] : self._titles[i] for i in range(len(self._ids)) }

        self._graph = nx.MultiDiGraph({self._ids[i] : self._links_to[i] for i in range(len(self._titles)) })
        self._node_index = {j[2] : Node(j[0],j[1],j[2],j[3],j[4]) for j in zip(self._fnames,
                                                                              self._titles,
                                                                              self._ids,
                                                                              self._tags,
                                                                              self._links_to)}

        self._orphans = [node for node in self._node_index.values()
                         if not any([node.links_to(other) for other in self._node_index.values()])]

        self._is_connected = self._orphans == []


    @property
    def graph(self) -> nx.MultiDiGraph:
        return self._graph

    @graph.setter
    def graph(self, value: nx.MultiDiGraph) -> nx.MultiDiGraph:
        self._graph = value

    @property
    def backlink_index(self) -> dict[str, list[str]]:
        return { node.id : node.links for node in self._node_index.values() }

    @property
    def file_index(self) -> dict[str, list[str]]:
        return {node.id : node.fname for node in self._node_index}

    @property
    def node_info(self) -> list[Node]:
        """
        Returns list of nodes
        """
        return self._node_index

    @node_info.setter
    def node_index(self, value : dict[str,Node]) -> dict[str,Node]:
        self._node_index = value

    def __init_ids(self, dbpath):
        """ Initializes list of IDs for each node
        Params
        dbpath -- str
              database path

        Returns list of roam-node ids
        """
        id_query = "SELECT id FROM nodes ORDER BY id ASC;"
        try:
            with sql.connect(dbpath, uri=True) as con:
                csr = con.cursor()
                query = csr.execute(id_query)
                return [i[0].replace('"', "") for i in query.fetchall()]

        except sql.Error as e:
            print("Connection failed: ", e)

    def __init_fnames(self, dbpath : str):
        """
        Initializes list of filenames for each node

        Params
        dbpath -- str
               database path


        Returns list of roam-node filepaths
        """
        fname_query = "SELECT file FROM nodes ORDER BY id ASC;"
        try:
            with sql.connect(dbpath, uri=True) as con:
                csr = con.cursor()
                query = csr.execute(fname_query)
                return [i[0].replace('"', "") for i in query.fetchall()]

        except sql.Error as e:
            print("Connection failed: ", e)

    def __init_titles(self, dbpath : str):
        """
        Initializes list of titles for each node

        Params
        dbpath -- str
               database path


        Returns list of roam-node titles
        """
        title_query = "SELECT title FROM nodes ORDER BY id ASC;"
        try:
            with sql.connect(dbpath, uri=True) as con:
                csr = con.cursor()
                query = csr.execute(title_query)
                return [i[0].replace('"', "") for i in query.fetchall()]

        except sql.Error as e:
            print("Connection failed: ", e)

    def __init_tags(self, dbpath : str):
        """
        Initializes list of tags for each node

        Params
        dbpath -- str
                database path

        Returns list of roam-node taglists (as a set)
        """
        tags_query = ("SELECT nodes.id, GROUP_CONCAT(tags.tag) AS tags FROM nodes LEFT JOIN tags ON nodes.id = tags.node_id GROUP BY nodes.id ORDER BY nodes.id ASC;")
        try:
            with sql.connect(dbpath, uri=True) as con:
                csr = con.cursor()
                query = csr.execute(tags_query)
                clean = lambda s: s.replace('"', "")
                match_null = lambda s : set() if not s else s.split(",")
                return [set(map(clean, match_null(i[1]))) for i in query.fetchall()]

        except sql.Error as e:
            print("Connection failed: ", e)

    def __init_links_to(self, dbpath : str):
        """
        Initializes list of links

        Params
        dbpath -- str
               database path


        Returns list of sets of roam-node links for each node
        """
        links_to_query = "SELECT n.id, GROUP_CONCAT(l.dest) FROM nodes n LEFT JOIN links l ON n.id = l.source GROUP BY n.id ORDER BY n.id ;"
        try:
            with sql.connect(dbpath, uri=True) as con:
                csr = con.cursor()
                query = csr.execute(links_to_query)
                clean = lambda s: s.replace('"', "")
                links = query.fetchall()

                return [([clean(i[0])] + list(map(clean, i[1].split(","))))
                        if i[1] else [clean(i[0])] for i in links]

        except sql.Error as e:
            print("Connection failed: ", e)

    def remove_orphans(self):
        """
        Removes orphan nodes

        Returns orphanless RoamGraph (not done in-place)
        """
        orphanless = copy.copy(self)
        not_orphan = lambda node: not self.__is_orphan(node)

        orphanless.nodes = list(filter(not_orphan, self.nodes))

        return orphanless

    @property
    def fnames(self, base : bool = True) -> list[str]:
        """
        Get list of filenames of graph

        base -- bool (True)
              basenames of files

        Returns list of filenames
        """
        if base:
            return [os.path.basename(node.fname) for node in self.node_info.values()]

        return [node._fname for node in self.nodes]

    @property
    def nodes(self) -> list[Node]:
        """
        Returns list of nodes
        """
        return list(self.node_info.values())

    @property
    def IDs(self) -> list[str]:
        """
        Returns list of node IDs
        """
        return [node.id for node in self.node_info.values()]

    @property
    def titles(self):
        """
        Returns list of node names (#+title file property)
        """
        return [node.title for node in self.nodes]

    @property
    def links(self):
        """
        Returns tuples of (title, links) for each node
        """
        links = [a.links for a in self.nodes]
        return [(a, b) for (a, b) in zip(self.titles, links)]

    def __is_orphan(self, node : Node):
        """
        Checks if node is an orphan with respect to others

        Params:
        node -- node to check orphanhood

        Returns True if node is orphan of self
        """
        pointed_to = True if any(node.id in n._links_to for n in self.nodes) else False
        points_to = node._links_to != {}
        return not points_to and not pointed_to


    def _identifier_type(self, identifier: str) -> IdentifierType:
        """
        Determines type of identifier
        """
        if identifier in self.titles:
            return IdentifierType.TITLE
        elif identifier in self.IDs:
            return IdentifierType.ID
        else:
            return IdentifierType.NOTHING


    def node_links(self , note_name : str) -> list[str]:
        if note_name not in self.note_index:
            raise AttributeError("No note with provided title")
        else:
            return self._node_index[note_name].links()


    def node(self, identifier: str) -> Node:
        """
        Grabs node from collection by identifier.
        Identifier can either be a note title or

        Parameters
        ---------
        identifier -- (str) node identifier, can be node ID or title
        """
        identifier_type = self._identifier_type(identifier)

        match identifier_type:
            case IdentifierType.TITLE:
                if identifier in self._duplicate_titles:
                    warnings.warn("This title is duplicated. This may not be the node you want",DuplicateTitlesWarning)
                idx = self.titles.index(identifier)
                return self.nodes[idx]
            case IdentifierType.ID:
                idx = self.Ids.index(identifier)
                return self.nodes[idx]
            case IdentifierType.NOTHING:
                raise AttributeError(f"No node with provided identifier: {identifier}")

        raise AttributeError("Uh oh spaghetti-o")

    def node_title(self, identifier : str) -> str:
        """
        Gets title of node

        Parameters
        ---------
        identifier -- (str) node ID to get title of
        """
        identifier_type = self._identifier_type(identifier)

        match identifier_type:
            case IdentifierType.ID:
                return self._id_title_map[identifier]


        raise AttributeError(f"No node with provided ID: {identifier}")


    def node_id(self, identifier : str) -> str:
        """
        Gets ID of node. Warns if title is duplicated in the collection

        Parameters
        ---------
        identifier -- (str) node title
        """
        identifier_type = self._identifier_type(identifier)

        match identifier_type:
            case IdentifierType.TITLE:
                if identifier_type in self._duplicate_titles:
                    warnings.warn("This title is duplicated. This may not be the ID you want.", DuplicateTitlesWarning)
                index_of_id = self._titles.index(identifier)
                return self.IDs[index_of_id]

        raise AttributeError(f"No node with provided title: {identifier}")
