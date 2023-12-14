from orgroamtools.RoamGraph import RoamGraph
from pprint import pp
import networkx as nx
import matplotlib.pyplot as plt
ROAM_DB = "~/.config/emacs/.local/cache/org-roam.db"

net = RoamGraph(ROAM_DB)
# undirectedned = nx.Graph(net.graph)




net = net.filter_tags(['category-theory', 'algebraic-geometry','lecture','fleeting','reference'])
print(len(net._node_index))
print(net._is_connected)
# for node in net._node_index.values():
#     print(f"Title: {node.title}\nID: {node.id}\nLinks: {node.links}")

link_map = net.backlink_index
net = nx.Graph(link_map)
net.remove_edges_from(list(nx.selfloop_edges(net)))
net.remove_edges_from(nx.selfloop_edges(net))
plt.cla()
plt.clf()
nx.draw(net, with_labels = False, node_size=25, width=0.2)
plt.savefig("viz/test.svg")
# print(len(net.node_index))
