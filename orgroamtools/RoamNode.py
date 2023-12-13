#!/usr/bin/env python3

import re

class RoamNode:
    """Node for org-roam zettels

    Attributes
    fname -- filename of node locatoin
    title -- title of node
    id    -- org-roam id
    tags  -- set of tags of node
    links_to -- set of ids this node links in its body
    """

    def __init__(self, fname, title, id, tags, links_to):
        """
        Params
        fname -- filename of node locatoin
        title -- title of node
        id    -- org-roam id
        tags  -- set of tags of node
        links_to -- set of ids this node links in its body
        """
        super(RoamNode, self).__init__()
        self.fname = fname
        self.title = title
        self.id = id
        self.tags = tags
        self.links_to = links_to

    @property
    def links(self, other_id):
        """
        Returns set of tags this node links to
        """
        return other_id in self.links_to

    def tags(self):
        """
        Returns node tags
        """
        return self.tags

    def links_to(self, n, directed=False):
        """
        Determined if node links to another node

            Params
            n -- RoamNode
                  other node
            directed -- bool.
                     check link directionally, otherwise return true
                        if other node likes to self

            Returns if node links to other node
        """

        if directed:
            return n.id in self.links_to
        else:
            return n.id in self.links_to or self.id in n.links_to

    @property
    def get_id(self):
        """
        Returns node id
        """
        return self.id

    @property
    def get_links(self):
        """
        Returns links of a node
        """
        return self.links_to

    @property
    def get_title(self):
        """
        Returns title of node
        """
        return self.title

    def has_tag(self, tags_checked):
        """
        Checks if node has tag

        Params
        tags_checked -- iterable (str)
            Iterable of tags to match exactly

        Returns True if node has any of the tags in tags_checked
        """
        return any(tag in tags_checked for tag in self.tags)

    def has_regex_tag(self, rxs):
        """
        Checks if node has regex tag

        Params
        rxs -- iterable (compiled regexes)
            Iterable of regexes to match

        Returns True if node tag matches any of the regexes
        """
        return any(rx.match(tag) for tag in self.tags for rx in rxs)

    def __str__(self):
        return f"({self.title}, {self.id})"

    def __repr__(self):
        return f"({self.title}, {self.id})"

    def __lt__(self,other):
        if not isinstance(other, RoamNode):
            return NotImplemented

        self.id < other.id


    def __gt__(self,other):
        if not isinstance(other, RoamNode):
            return NotImplemented

        self.id > other.id
