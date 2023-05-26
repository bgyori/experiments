# %%[markdown]
# Author: Nelson Liu
# 
# Email: [nliu@uncharted.software](mailto:nliu@uncharted.software)

# %%[markdown]
# Convert between a model's AMR (ASKEM Model Representation) and its ODE representation (MathML)
#
# Equation-to-Model: [https://github.com/ml4ai/skema/tree/main/skema/skema-rs/mathml](https://github.com/ml4ai/skema/tree/main/skema/skema-rs/mathml)

# %%
import html
import re
import os
import json
import requests
from tqdm import tqdm
import numpy as np
import pandas as pd
import networkx as nx
import matplotlib as mpl
import matplotlib.pyplot as plt
from typing import NoReturn, Optional, Any
import latex2mathml.converter

# %%
REST_URL_SKEMA = "https://skema-rs.staging.terarium.ai"

# %%
# Helper functions

# Convert LaTeX equations to MathML equations
def convert_latex2mathml(model_latex: Optional[list]) -> list:

    model_mathml = []
    for i in range(len(model_latex)):

        m = latex2mathml.converter.convert(model_latex[i])

        # Replace some unicode characters
        # SKEMA throws error otherwise
        # m = m.replace('&#x0003D;', '=') 
        # m = m.replace('&#x02212;', '-')
        # m = m.replace('&#x0002B;', '+')
        m = html.unescape(m)

        model_mathml.append(m)
        
    return model_mathml

# Convert MathML equations to Petri-net AMR
def convert_mathml2petrinet(model_mathml: Optional[list] = None) -> dict:

    model_petrinet_amr = {}

    # SKEMA API health check
    if model_mathml == None:
        url = f'{REST_URL_SKEMA}/ping'
        res = requests.get(url)
        print(f'{res.url}: Code {res.status_code}\n\t\"{res.text}\"')

    # SKEMA API for MathML-to-AMR conversion
    else:
        url = f'{REST_URL_SKEMA}/mathml/acset'
        res = requests.put(url, json = model_mathml)
        print(f'{res.url}: Code {res.status_code}\n\t\"{res.text}\"')
        if res.status_code == 200:
            model_petrinet_amr = res.json()

    return model_petrinet_amr

# Draw Petri net using NX
def draw_graph(model: dict, ax: Optional[Any] = None, node_type: Optional[list] = None, edge_type: Optional[list] = None, save_path: Optional[str] = None, legend: bool = True, model_format: Optional[str] = 'AMR') -> NoReturn:

    # Build graph

    # ACSet format
    if model_format == 'acset':

        map_petrinet_names = {
            'S': {(i + 1): s['sname'] for i, s in enumerate(model['S'])}, 
            'T': {(j + 1): s['tname'] for j, s in enumerate(model['T'])}
        }

        # Node list
        df_nodes = pd.DataFrame({
            'id': [s['sname'] for s in model['S']] + [s['tname'] for s in model['T']],
            'type': ['S' for s in model['S']] + ['T' for s in model['T']]
        })

        # Edge list
        df_edges = pd.DataFrame({
            'source': [map_petrinet_names['S'][d['is']] for d in model['I']] + [map_petrinet_names['T'][d['ot']] for d in model['O']],
            'source_type': ['S' for d in model['I']] + ['T' for d in model['O']],
            'target': [map_petrinet_names['T'][d['it']] for d in model['I']] + [map_petrinet_names['S'][d['os']] for d in model['O']],
            'target_type': ['T' for d in model['I']] + ['S' for d in model['O']],
            'edge_type': ['I' for d in model['I']] + ['O' for d in model['O']]
        })

    # ASKEM Model Representation (AMR) format
    if model_format == 'AMR':

        # Node list
        df_nodes = pd.DataFrame(
            [{'id': state['id'], 'type': 'S'} for state in model['model']['states']] + [{'id': trans['id'], 'type': 'T'} for trans in model['model']['transitions']]
        )

        # Edge list
        df_edges = pd.DataFrame(
            [{'id': '', 'source': state_id, 'target': trans['id'], 'edge_type': 'I'} for trans in model['model']['transitions'] for state_id in trans['input']] + [{'id': '', 'source': trans['id'], 'target': state_id, 'edge_type': 'O'} for trans in model['model']['transitions'] for state_id in trans['output']]
        )

    # Build graph
    G = nx.DiGraph()
    G.add_nodes_from([(node['id'], {'id': node['id'], 'type': node['type']}) for __, node in df_nodes.iterrows()])
    G.add_edges_from([(edge['source'], edge['target'], {'id': id, 'type': edge['edge_type']}) for id, edge in df_edges.iterrows()])


    # Draw graph

    # Colors
    # node_colors = mpl.cm.Pastel1(plt.Normalize(0, 8)(range(8)))
    edge_colors = mpl.cm.tab10(plt.Normalize(0, 10)(range(10)))

    # Layout
    # pos = nx.kamada_kawai_layout(G)
    # pos = nx.spring_layout(G, k = 0.5)
    nlist = [
        [node[0] for node in G.nodes.data(True) if node[1]['type'] == 'S'], 
        [node[0] for node in G.nodes.data(True) if node[1]['type'] == 'T']
    ]
    pos = nx.shell_layout(G, nlist = nlist)


    if node_type == None:
        map_node_type = {x: i for i, x in enumerate(set([type(node[1]['type']) for node in G.nodes.data(True)]))}

        if len(map_node_type) == 1:
            map_node_type = {x: i for i, x in enumerate(set([node[1]['type'] for node in G.nodes.data(True)]))}
            node_type = [map_node_type[node[1]['type']] for node in G.nodes.data(True)]
        else:
            node_type = [map_node_type[type(node[1]['type'])] for node in G.nodes.data(True)]

    if edge_type == None:
        map_edge_type = {x: i for i, x in enumerate(set([edge[2]['type'] for edge in G.edges.data(True)]))}
        edge_type = [map_edge_type[edge[2]['type']] for edge in G.edges.data(True)]

    if ax == None:
        fig, ax = plt.subplots(1, 1, figsize = (8, 8))

    h = []

    for t, i in map_node_type.items():
        h.append(nx.draw_networkx_nodes(
            ax = ax, 
            G = G, 
            pos = pos,
            nodelist = [node for node, nt in zip(G.nodes, node_type) if nt == i],
            node_color = [i for node, nt in zip(G.nodes, node_type) if nt == i], 
            # node_size = i * 500 + 100,
            node_size = 100,
            cmap = mpl.cm.Pastel1, vmin = 0, vmax = 8,
            alpha = 0.8,
            label = t
        ))

    for t, i in map_edge_type.items():
        __ = nx.draw_networkx_edges(
            ax = ax,
            G = G,
            pos = pos,
            arrows = True,
            edgelist = [edge[:2] for edge in G.edges.data(True) if edge[2]['type'] == t], 
            label = t,
            edge_color = [i for edge in G.edges.data(True) if edge[2]['type'] == t],
            edge_cmap = mpl.cm.tab10,
            edge_vmin = 0, edge_vmax = 10,
            connectionstyle = 'arc3,rad=0.2'
        )

    __ = nx.draw_networkx_labels(
        ax = ax,
        G = G, 
        pos = pos,
        labels = {node: node for node in G.nodes},
        font_size = 8
    )

    M = np.max(np.nanmax(np.array(list(pos.values())), axis = 0))
    m = np.min(np.nanmin(np.array(list(pos.values())), axis = 0))
    m = 1.5 * max([np.abs(M), np.abs(m)])
    __ = plt.setp(ax, xlim = (-m, m), ylim = (-m, m))

    if legend == True:
        __ = ax.legend(handles = h + [mpl.patches.FancyArrow(0, 0, 0, 0, color = edge_colors[i, :], width = 1) for t, i in map_edge_type.items()], labels = list(map_node_type.keys()) + list(map_edge_type.keys()), loc = 'upper center', bbox_to_anchor = (0.5, -0.01), ncols = 4)

    if save_path != None:
        fig.savefig(save_path, dpi = 150)

# %%[markdown]
# ## Test with SIR model

# %%
model_name = 'SIR'
models = {}
models[model_name] = {}

# LaTeX
models[model_name]['latex'] = [
    r"\frac{d S}{d t} = -\beta S I",
    r"\frac{d I}{d t} = \beta S I - \gamma I",
    r"\frac{d R}{d t} = \gamma I"
]

# MathML
models[model_name]['latex_mathml'] = convert_latex2mathml(models[model_name]['latex'])

# %%
# AMR Petri net
models[model_name]['latex_mathml_AMR'] = convert_mathml2petrinet(models[model_name]['latex_mathml'])

# %%
draw_graph(model = models[model_name]['latex_mathml_AMR'], legend = True, model_format = 'AMR')

# %%[markdown]
# ## Test with SIDARTHE

# %%
model_name = 'BIOMD0000000955'
models[model_name] = {}

with open('../../thin-thread-examples/mira_v2/biomodels/BIOMD0000000955/model_askenet.json', 'r') as f:
    models[model_name]['AMR'] = json.load(f)

# %%
# SIDARTHE equations in LaTeX
model_name = 'SIDARTHE'
models[model_name] = {}

models[model_name]['latex'] = [
    r"\frac{d S}{d t} = - \alpha S I - \beta S D - \gamma S A - \delta S R",
    r"\frac{d I}{d t} = \alpha S I + \beta S D + \gamma S A + \delta S R - \epsilon I - \zeta I - \lambda I",
    r"\frac{d D}{d t} = \epsilon I - \eta D - \rho D",
    r"\frac{d A}{d t} = \zeta I - \theta A - \mu A - \kappa A",
    r"\frac{d R}{d t} = \eta D + \theta A - \nu R - \xi R",
    r"\frac{d T}{d t} = \mu A + \nu R - \sigma T - \tau T",
    r"\frac{d H}{d t} = \lambda I + \rho D + \kappa A + \xi R + \sigma T",
    r"\frac{d E}{d t} = \tau T",
]

# %%
# Convert LaTeX equations to MathML equations
models[model_name]['latex_mathml'] = convert_latex2mathml(models[model_name]['latex'])

# %%
# Convert MathML equations to Petri net (AMR)
models[model_name]['latex_mathml_AMR'] = convert_mathml2petrinet(models[model_name]['latex_mathml']) 

# %%
draw_graph(model = models[model_name]['latex_mathml_AMR'], legend = True, model_format = 'AMR')

# %%
