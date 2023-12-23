#!/usr/bin/env python3

from orgroamtools.RoamGraph import RoamGraph
import matplotlib.pyplot as plt
import matplotlib.cm as cm
import matplotlib.colors as colors
import networkx as nx
import numpy as np


ROAM_DB = "tests/org-roam.db"

# List of tags to filter by
tags = []

network = RoamGraph(ROAM_DB).filter_tags(["reference", "lecture"], exclude=True)
G = nx.Graph(network.graph)


def pretty_plot_graph(G):
    deg_centrality = nx.degree_centrality(G)
    cent = np.fromiter(deg_centrality.values(), float)
    sizes = cent / np.max(cent) * 200
    normalize = colors.Normalize(vmin=cent.min(), vmax=cent.max())
    colormap = cm.viridis

    scalarmappaple = cm.ScalarMappable(norm=normalize, cmap=colormap)
    scalarmappaple.set_array(cent)

    # pos = nx.random_layout(G)
    # pos = nx.fruchterman_reingold_layout(G,k=0.2)
    pos = nx.spring_layout(G)
    plt.cla()
    plt.clf()
    nx.draw(G, pos, node_size=sizes, node_color=sizes, cmap=colormap, width=0.2)
    plt.show()
    plt.savefig("images/COVER.svg")


pretty_plot_graph(G)
