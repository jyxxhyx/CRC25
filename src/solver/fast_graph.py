"""
Fast graph update: instead of rebuilding the entire graph via momepy.gdf_to_nx,
copies the parent graph and updates only the changed edges.

Key insight: each child node modifies only 1 arc → only needs to update 1-2 edges.
G.copy() takes ~4ms vs create_network_graph takes ~300ms → 72x speedup.
"""
import networkx as nx
from src.utils.common_utils import correct_arc_direction
from src.utils.dataparser import handle_weight_with_recovery, create_network_graph


def fast_calc_sub_best(problem_node):
    """
    Fast version of ProblemNode.calc_sub_best for child nodes (level > 0).
    Copies parent graph and incrementally updates changed edges.
    Falls back to slow path for root node.
    """
    solver = problem_node.org_solver
    config = problem_node.config
    
    # Root node or no parent graph: use slow path
    if problem_node.master is None or not hasattr(problem_node.master, 'new_graph') or problem_node.master.new_graph is None:
        problem_node.weight_df = handle_weight_with_recovery(problem_node.map_df, config.user_model)
        _, problem_node.new_graph = create_network_graph(problem_node.weight_df)
    else:
        # Fast path: copy parent graph and update changed edges
        problem_node.new_graph = problem_node.master.new_graph.copy()
        
        # Apply modifications to graph edges
        id_point_map = solver.data_holder.id_point_map
        for (i, j), modify_tag in problem_node.modified_arc_list:
            _update_edges_in_graph(problem_node.new_graph, i, j, modify_tag, 
                                   solver, config, id_point_map)
    
    # Route finding is the same
    problem_node.path_best, problem_node.G_path_best, problem_node.df_path_best = \
        solver.router.get_route(
            problem_node.new_graph,
            solver.data_holder.start_node_lc,
            solver.data_holder.end_node_lc,
            solver.heuristic_f
        )
    problem_node.df_path_best = correct_arc_direction(
        problem_node.df_path_best,
        solver.data_holder.start_node_id,
        solver.data_holder.end_node_id
    )


def _recalc_weight(edge_data, user_model, new_path_type=None):
    """Recalculate my_weight for an edge based on its attributes."""
    length = edge_data.get('length', 1)
    weight = length
    crossing = edge_data.get('crossing', 'No')
    if crossing == 'Yes':
        weight = length * user_model.get('crossing_weight_factor', 1)
    
    path_type = new_path_type or edge_data.get('path_type', 'walk')
    pref = user_model.get('walk_bike_preference', 'walk')
    pref_factor = user_model.get('walk_bike_preference_weight_factor', 1)
    if pref == 'walk' and path_type == 'walk':
        weight *= pref_factor
    elif pref == 'bike' and path_type == 'bike':
        weight *= pref_factor
    
    return weight


def _update_edges_in_graph(G, arc_i, arc_j, modify_tag, solver, config, id_point_map):
    """Update edge attributes in graph for a modified arc."""
    from src.solver.ArcModifyTag import ArcModifyTag
    
    u_coord = id_point_map.get(arc_i)
    v_coord = id_point_map.get(arc_j)
    if u_coord is None or v_coord is None:
        return
    
    user_model = config.user_model
    
    # For bidirectional edges, update both directions
    directions = [(u_coord, v_coord)]
    # Check if it's a sidewalk (bidirectional)
    # We check if reverse edge exists
    if G.has_edge(v_coord, u_coord):
        directions.append((v_coord, u_coord))
    
    for u, v in directions:
        if not G.has_edge(u, v):
            continue
        for key in list(G[u][v].keys()):
            edge_data = G[u][v][key]
            
            if modify_tag == ArcModifyTag.TO_INFE:
                edge_data['include'] = 0
                # Set very high weight to make Dijkstra avoid it
                # Keep original weight for reference
                edge_data['_original_weight'] = edge_data.get('_original_weight', edge_data['my_weight'])
                edge_data['my_weight'] = 1e9
                # Update obstacle_free_width_float
                min_width = user_model.get('min_sidewalk_width', 1.5)
                edge_data['obstacle_free_width_float'] = max(min_width - 1, 0)
                
            elif modify_tag == ArcModifyTag.TO_FE:
                edge_data['include'] = 1
                # Restore weight
                orig = edge_data.pop('_original_weight', None)
                if orig is not None:
                    edge_data['my_weight'] = orig
                else:
                    edge_data['my_weight'] = _recalc_weight(edge_data, user_model)
                # Update attributes
                edge_data['curb_height_max'] = user_model.get('max_curb_height', 0.03)
                edge_data['obstacle_free_width_float'] = user_model.get('min_sidewalk_width', 1.5)
                
            elif modify_tag == ArcModifyTag.CHANGE:
                old_type = edge_data.get('path_type', 'walk')
                new_type = 'bike' if old_type == 'walk' else 'walk'
                edge_data['path_type'] = new_type
                edge_data['my_weight'] = _recalc_weight(edge_data, user_model, new_type)
