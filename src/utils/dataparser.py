# encoding:utf-8
"""
@email  :    lvxiangdong2qq@163.com
@auther :    XiangDongLv
@time   :    2025/7/8 16:27
@project:    CRC25
"""


import json

import momepy
import networkx as nx
import numpy as np
from shapely import from_wkt, to_wkt


def handle_weight(df, user_model):
    # Don't include crossings with curbs that are too high
    df.loc[df['curb_height_max'] > user_model["max_curb_height"], 'include'] = 0

    # Don't include paths that are too narrow
    df.loc[df['obstacle_free_width_float'] < user_model["min_sidewalk_width"], 'include'] = 0

    # Define weight (combination of objectives)
    df['my_weight'] = df['length']

    df.loc[df['crossing'] == 'Yes', 'my_weight'] = df['length'] * user_model["crossing_weight_factor"]

    if user_model["walk_bike_preference"] == 'walk':
        df.loc[df['path_type'] == 'walk', 'my_weight'] = df['my_weight'] * user_model[
            "walk_bike_preference_weight_factor"]
    elif user_model["walk_bike_preference"] == 'bike':
        df.loc[df['path_type'] == 'bike', 'my_weight'] = df['my_weight'] * user_model[
            "walk_bike_preference_weight_factor"]

    df['my_weight'] = df['my_weight'] / df['my_weight'].abs().max()
    return df


def handle_weight_with_recovery(df, user_model):
    # Include paths that satisfy the following conditions
    df.loc[df['curb_height_max'] <= user_model["max_curb_height"], 'include'] = 1

    df.loc[df['obstacle_free_width_float'] >= user_model["min_sidewalk_width"], 'include'] = 1

    # Don't include crossings with curbs that are too high
    df.loc[df['curb_height_max'] > user_model["max_curb_height"], 'include'] = 0

    # Don't include paths that are too narrow
    df.loc[df['obstacle_free_width_float'] < user_model["min_sidewalk_width"], 'include'] = 0

    # Define weight (combination of objectives)
    df['my_weight'] = df['length']

    df.loc[df['crossing'] == 'Yes', 'my_weight'] = df['length'] * user_model["crossing_weight_factor"]

    if user_model["walk_bike_preference"] == 'walk':
        df.loc[df['path_type'] == 'walk', 'my_weight'] = df['my_weight'] * user_model[
            "walk_bike_preference_weight_factor"]
    elif user_model["walk_bike_preference"] == 'bike':
        df.loc[df['path_type'] == 'bike', 'my_weight'] = df['my_weight'] * user_model[
            "walk_bike_preference_weight_factor"]

    df['my_weight'] = df['my_weight'] / df['my_weight'].abs().max()
    return df


def create_network_graph(df):
    """Build directed multigraph from filtered (include=1) rows only.
    Optimized: skip unused G_con_dir construction."""
    df_sel = df[df['include'] == 1]
    import warnings

    with warnings.catch_warnings():
        warnings.filterwarnings("ignore", category=RuntimeWarning)
        G_sel = momepy.gdf_to_nx(df_sel, approach="primal", multigraph=True)

    # Get subgraphs for connectivity
    S_sel = [G_sel.subgraph(c).copy() for c in sorted(nx.connected_components(G_sel), key=len, reverse=True)]

    if len(S_sel) > 1:
        G_sel_con = nx.compose(S_sel[0], S_sel[1])
    else:
        G_sel_con = G_sel

    # Convert back to GeoDataFrame for oneway processing
    with warnings.catch_warnings():
        warnings.filterwarnings("ignore", category=RuntimeWarning)
        G_sel_con_df = momepy.nx_to_gdf(G_sel_con, points=False, lines=True)

    # Make bi-directionality of sidewalks (and not of bike paths) explicit
    G_sel_con_df['oneway'] = np.where(G_sel_con_df['bikepath_id'].isna(), False, True)

    # Create directed graph
    with warnings.catch_warnings():
        warnings.filterwarnings("ignore", category=RuntimeWarning)
        G_sel_con_dir = momepy.gdf_to_nx(G_sel_con_df, approach="primal", multigraph=True, directed=True,
                                         oneway_column="oneway")

    return None, G_sel_con_dir


def store_op_list(store_path, route_name, route_id, op_list):
    with open(f'{store_path}route_op_{route_name}_{route_id}.json', 'w') as f:
        json.dump(op_list, f)


def load_op_list(store_path, route_name, route_id):
    with open(f'{store_path}route_op_{route_name}_{route_id}.json', 'r') as f:
        op_list = json.load(f)
    op_list = [(op[0], (op[1][0], from_wkt(op[1][1])), op[2], op[3]) for op in op_list if op[3] == "success"]
    return op_list


def convert(obj):
    if isinstance(obj, np.integer):
        return int(obj)
    elif isinstance(obj, np.floating):
        return float(obj)
    elif isinstance(obj, np.ndarray):
        return obj.tolist()
    else:
        return obj


def convert_op_list_to_wkt(op_list):
    available_op = [
        (op[0], (convert(op[1][0]), to_wkt(op[1][1].iloc[0], rounding_precision=-1, trim=False)), convert(op[2]), op[3])
        for op in op_list if op[3] == "success"]
    return available_op