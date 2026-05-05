import sys,os,yaml,time
sys.path.insert(0,'.')
with open('config.yaml','r',encoding='utf-8') as f: yc=yaml.safe_load(f)
yc['paths']['route_name']='nwmkt_t_1_3'
from config import Config; c=Config(yc,base_dir='.'); c.load_from_yaml()
from src.solver.BaseSolver import BaseSolver
from src.AlgoTimer import AlgoTimer
from src.utils.dataparser import handle_weight_with_recovery, create_network_graph
t=AlgoTimer(time.time()); s=BaseSolver(c,t); s.init_from_config()

# Build arc->graph_edge mapping from root graph
G = s.org_graph
ipm = s.data_holder.id_point_map
df = s.org_map_df

# Build mapping: arc (int_id_i, int_id_j) -> list of (u, v, key) in graph
arc_to_edges = {}
graph_edge_to_arc = {}
for u, v, k, d in G.edges(data=True, keys=True):
    # Find which arc this edge belongs to by geometry matching
    # Each map_df row has geometry, each graph edge has geometry
    pass

# Different approach: build from map_df -> root_problem.new_graph
# Let's trace through root_problem creation
from src.solver.SearchSolver import SearchSolver
from src.solver.ProblemNode import ProblemNode
from src.TrackedCounter import TrackedCounter
from src.solver.Operator import do_foil_must_be_feasible
solver = SearchSolver(c, t)
solver.init_from_config()
solver.analyzer.do_basic_analyze()
foil_arcs = do_foil_must_be_feasible(solver)
counter = TrackedCounter(start=0, step=1)
from src.solver.SearchSolver import SearchSolver
root_info = solver.process_data_for_root_problem()
root = ProblemNode(solver, root_info, foil_arcs, solver.current_solution_map, solver.org_graph, None, counter, 0)
root.apply_modified_arc()
root.calc_sub_best()

G2 = root.new_graph
print(f"Root new_graph: nodes={G2.number_of_nodes()}, edges={G2.number_of_edges()}")
print(f"Root graph type: {type(G2).__name__}")

# Now check: does arc from map_df map to edge in this graph?
for idx, row in df.head(50).iterrows():
    i, j = row['arc']
    u_coord, v_coord = ipm[i], ipm[j]
    if G2.has_edge(u_coord, v_coord):
        keys = list(G2[u_coord][v_coord].keys())
        print(f"Arc ({i},{j}) -> edges: {[(u_coord,v_coord,k) for k in keys]}")
        break
    elif G2.has_edge(v_coord, u_coord):
        keys = list(G2[v_coord][u_coord].keys())
        print(f"Arc ({i},{j}) -> REVERSE edges: {[(v_coord,u_coord,k) for k in keys]}")
        break
else:
    print("No arc found in first 50 rows")

# Try: how many map_df rows have arcs that exist in G2?
found = 0
for idx, row in df.iterrows():
    i, j = row['arc']
    if i is None or j is None: continue
    u, v = ipm.get(i), ipm.get(j)
    if u and v and (G2.has_edge(u, v) or G2.has_edge(v, u)):
        found += 1
print(f"Map rows with arcs in G2: {found}/{len(df)}")
