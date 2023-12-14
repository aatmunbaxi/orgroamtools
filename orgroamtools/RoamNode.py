#!/usr/bin/env python3

import re
from typing import Iterable

class RoamNode:
    """Node for org-roam zettels

    Attributes
    fname -- filename of node locatoin
    title -- title of node
    id    -- org-roam id
    tags  -- set of tags of node
    links_to -- set of ids this node links in its body
    """

    def __init__(self, fname : str,
                 title : str,
                 id : str,
                 tags : set[str],
                 links_to : set[str]):
        """
        Params
        fname -- filename of node locatoin
        title -- title of node
        id    -- org-roam id
        tags  -- set of tags of node
        links_to -- set of ids this node links in its body
        """
        super(RoamNode, self).__init__()
        self._fname = fname
        self._title = title
        self._id = id
        self._tags = tags
        self._links_to = links_to

    @property
    def links(self, other_id : str):
        """
        Returns set of tags this node links to
        """
        return other_id in self._links_to

    @property
    def fname(self) -> str:
        return self._fname

    @property
    def tags(self):
        """
        Returns node tags
        """
        return self._tags


    def links_to(self, n , directed : bool = False):
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
            return n._id in self._links_to
        else:
            return n._id in self._links_to or self._id in n._links_to

    @property
    def id(self):
        """
        Returns node id
        """
        return self._id

    @property
    def links(self) -> set[str]:
        """
        Returns links of a node
        """
        return self._links_to

    @property
    def title(self) -> str:
        """
        Returns title of node
        """
        return self._title

    def has_tag(self, tags_checked : Iterable[str]) -> bool:
        """
        Checks if node has tag

        Params
        tags_checked -- iterable (str)
            Iterable of tags to match exactly

        Returns True if node has any of the tags in tags_checked
        """
        return any(tag in tags_checked for tag in self.tags)

    def has_regex_tag(self, rxs : Iterable[str]) -> bool:
        """
        Checks if node has regex tag

        Params
        rxs -- iterable
            Iterable of regexes to match

        Returns True if node tag matches any of the regexes
        """
        return any(rx.match(tag) for tag in self.tags for rx in rxs)

    def __str__(self):
        return f"({self._title}, {self._id})"

    def __repr__(self):
        return f"({self._title}, {self._id})"

    def __lt__(self,other) -> bool:
        if not isinstance(other, RoamNode):
            return NotImplemented

        self._id < other.id


    def __gt__(self,other) -> bool:
        if not isinstance(other, RoamNode):
            return NotImplemented

        self.id > other.id
