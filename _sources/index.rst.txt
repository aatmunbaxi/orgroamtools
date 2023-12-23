orgroamtools documentation
========================================

``orgroamtools`` is a work-in-progress replication of ``obsidiantools``--a Python library to assist in data analysis of Obsidian collections--but for ``org-roam`` collections.

===============
Getting Started
===============
Ensure your ``org-roam v2`` database is up-to-date by running ``(org-roam-db-sync)`` inside Emacs. Locate your database by checking the value of ``(org-roam-db-location)``.
Once you've imported the ``RoamGraph`` object, you can load your collection::

  from orgroamtools.data import RoamGraph

  collection = RoamGraph(PATH_TO_DB)


-------------
Data Provided
-------------
The central object is the ``RoamGraph`` object, which stores a collection of ``RoamNode`` objects and the graph structure they create via backlinks.
The data contained in the ``RoamNode`` includes its ``ID`` given by ``org-mode``, its title, the file it resides in, the org-tags it has, its list of backlinks to other nodes, and the list of other org-links that are not backlinks.

-------
Indices
-------
An *index* refers to an object of type ``dict[str, T]`` where the keys are IDs of nodes and ``T`` is some information about the node with the associated ID.
The library provides several indices:

- ``node_index``: ``T`` is the ``RoamNode`` of the node with corresponding ID

- ``title_index``: ``T`` is the title of the node

- ``tag_index``: ``T`` is the set of tags a node has

- ``backlink_index``: ``T`` is the list of backlinks to other nodes in the node

- ``file_index``: ``T`` is the filename where the node is located

- ``misc_link_index``: ``T`` is a list of other org-links that are not backlinks. e.g. links to files, websites, etc

- Indices extracting from the body text of the node:

  - ``body_index`` : ``T`` is the body of the node
  - ``math_snippet_index`` : ``T`` is a list of LaTeX snippets inside the node

    - Supported delimiters include ``\(\)``, ``\[\]``, and ``equation, align, multiline`` environments. In addition, ``#+begin_equation`` and ``#+begin_latex`` blocks are supported
  - ``src_block_index`` : ``T`` is a list of tuples ``(S,W)`` where ``S`` is the language of the source block and ``W`` is the content of the source block

As an example of how to use these indices, let's make our own ``backlink_index`` but instead of using lists of org IDs for the backlink lists, we'll make them the title of the nodes.
The ``title_index`` property provides a mapping from ``ID -> title``, so we could make it a simple one-liner::

  net = RoamGraph(PATH_TO_DB)
  backlink_index_titles = {node.id : [net.title_index[ID]
                            for ID in node.backlinks] for node in net.nodes}


---------------
NetworkX Graph
---------------

The ``RoamGraph`` object also provides a ``networkx.MultiDiGraph`` representation of the network. The ``networkx`` library is very feature-rich for graph manipulations, and can be used to create nice visualization such as this:

.. image:: ../../viz/COVER.svg

------------------------------
Manipulation of the Collection
------------------------------
In addition to this information, primitive manipulations of the collection are provided, such as filtering the collection by tag, and removal of orphans from the collection.

For more complex manipulations, we can use the setter :func:`orgroamtools.data.RoamGraph.node_index` to manually set the ``_node_index`` attribute after any manipulation on the nodes, then use :func:`orgroamtools.data.RoamGraph.refresh` to update remaining attributes.

For example, let's say we want to remove a single node with ID ``foo`` from a collection ``bar``.
To do this, we'd have to remove the key ``foo`` from the ``_node_index`` of ``bar``, then delete all backlinks to the node ``foo`` from all nodes in the index.
We could accomplish that like this::

  index = bar.node_index()
  del index["foo"]

  for node in index.values():
      if "foo" in node.backlinks:
          node.backlinks.remove("foo")

  bar.nodex_index(index)
  bar.refresh()

The collection ``bar`` will now have the node ``foo`` deleted, along with any backlinks to the node ``foo``.

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
