import os, glob, re
import warnings
import sqlite3 as sql
import copy

from orgroamtools.RoamNode import RoamNode as Node


class RoamGraph:
    """
    Stores information of a (possibly filtered) roam directory.

    Attributes
    -----------
    db : str
        path to org-roam-db
    nodes : list RoamNode
        list of RoamNodes
    """

    def __init__(self, db):
        """
        Constructor for RoamGraph

        Params
        db -- path to org-roam db (required)
        """

        super(RoamGraph, self).__init__()

        self.db_path = os.path.expanduser(db)

        fnames = self.__init_fnames(self.db_path)
        titles = self.__init_titles(self.db_path)
        ids = self.__init_ids(self.db_path)
        tags = self.__init_tags(self.db_path)
        links_to = self.__init_links_to(self.db_path)

        self.node_index = titles

        self.graph = {titles[i] : links_to[i] for i in range(len(titles)) }
        self.node_info = {j[1] : Node(j[0],j[1],j[2],j[3],j[4]) for j in zip(fnames,titles,ids,tags,links_to)}


    @property
    def get_graph(self):
        return self.graph


    @property
    def get_node_info(self):
        """
        Returns list of nodes
        """
        return self.node_info


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

    def __init_fnames(self, dbpath):
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

    def __init_titles(self, dbpath):
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

    def __init_tags(self, dbpath):
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

    def __init_links_to(self, dbpath):
        """
        Initializes list of links

        Params
        dbpath -- str
               database path


        Returns list of roam-node links
        """
        links_to_query = "SELECT n.id, GROUP_CONCAT(l.dest) FROM nodes n LEFT JOIN links l ON n.id = l.source GROUP BY n.id ORDER BY n.id ;"
        try:
            with sql.connect(dbpath, uri=True) as con:
                csr = con.cursor()
                query = csr.execute(links_to_query)
                clean = lambda s: s.replace('"', "")
                links = query.fetchall()

                return [set(map(clean, i[1].split(","))) if i[1] else {} for i in links]

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
    def fnames(self, base=True) -> list[str]:
        """
        Get list of filenames of graph

        base -- bool (True)
              basenames of files

        Returns list of filenames
        """
        if base:
            return [os.path.basename(node.fname) for node in self.node_info.values()]

        return [node.fname for node in self.nodes]

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
        links = [a.get_links() for a in self.nodes()]
        return [(a, b) for (a, b) in zip(self.titles(), links)]

    def __is_orphan(self, node):
        """
        Checks if node is an orphan with respect to others

        Params:
        node -- node to check orphanhood

        Returns True if node is orphan of self
        """
        pointed_to = True if any(node.id in n.links_to for n in self.nodes) else False
        points_to = node.links_to != {}
        return not points_to and not pointed_to

    def note_links(self , note_name: str) -> list[str]:
        if note_name not in self.note_index:
            raise AttributeError("No note with this name")
        else:
            return self.node_info[note_name].links()
