.. orgroamtools documentation master file, created by
   sphinx-quickstart on Tue Dec 19 14:36:33 2023.
   You can adapt this file completely to your liking, but it should at least
   contain the root `toctree` directive.

Welcome to orgroamtools's documentation!
========================================
This library is meant to assist in any analysis of the natural graph structure created out of org-roam collections. It allows access to basic information of the graph like its nodes, links between nodes, and information about those nodes.

The primary object of focus is the ``RoamGraph`` class in the ``data`` module. It stores the graph structure and relevant information about its nodes, and provides a ``networkx`` representation of the directed multigraph structure of the collection.

To get started, ensure your ``org-roam`` database file is up to date by running ``(org-roam-db-sync)`` inside emacs. Then locate the ``org-roam.db`` file. You're now ready to load the graph structure::

  from orgroamtools.data import RoamGraph

  collection = RoamGraph(PATH_TO_org-roam.db")

.. toctree::
   :maxdepth: 1
   :caption: Contents:

   modules


Indices and tables
==================

* :ref:`genindex`
* :ref:`modindex`
* :ref:`search`
