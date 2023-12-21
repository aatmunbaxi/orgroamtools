Welcome to orgroamtools's documentation!
========================================

``orgroamtools`` is a work-in-progress clone of ``obsidiantools``--a Python library to assist in analysis of Obsidian collection--but for ``org-roam``.
The main tool to go about this is the ``orgroamtools.data.RoamGraph`` object, which stores all the information necessary to produce the natural multidirected graph structure of your digital zettelkasten.

===============
Getting Started
===============
Ensure your ``org-roam v2`` database is up-to-date by running ``(org-roam-db-sync)`` inside Emacs. Locate your database by checking the value of ``(org-roam-db-location)``.
Once you've imported the ``RoamGraph`` object, you can load your collection::

  from orgroamtools.data import RoamGraph

  collection = RoamGraph(PATH_TO_DB)

-------------
General Notes
-------------
Because ``org-roam`` allows you to have multiple nodes with the same title, the ID of a node is guaranteed to uniquely identify a node in your collection.
For user ergonomics, you are permitted to identify nodes by their title.
For example, in the :func:`orgroamtools.data.RoamGraph.node` function, the ``identifier`` argument can be either a node title or node ID.
If the network detects multiple nodes with the same title and you attempt to identify a node by the duplicated title, you will be warned that it might not be the output you wanted.

.. automodule::orgroamtools.data
   :members:

.. automodule::orgroamtools._utils
   :members:
   :private-members:
   :special-members:

.. toctree::
   :maxdepth: 3
   :caption: Contents:

   orgroamtools


Indices and tables
==================

* :ref:`genindex`
* :ref:`search`
