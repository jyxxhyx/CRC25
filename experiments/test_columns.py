import sys,os,yaml,time
sys.path.insert(0,'.')
with open('config.yaml','r',encoding='utf-8') as f: yc=yaml.safe_load(f)
yc['paths']['route_name']='nwmkt_t_1_3'
from config import Config; c=Config(yc,base_dir='.'); c.load_from_yaml()
from src.solver.BaseSolver import BaseSolver
from src.AlgoTimer import AlgoTimer
from src.solver.SearchSolver import SearchSolver
from src.solver.ProblemNode import ProblemNode
from src.TrackedCounter import TrackedCounter
from src.solver.Operator import do_foil_must_be_feasible

timer = AlgoTimer(time.time())
solver = SearchSolver(c, timer)
solver.init_from_config()
solver.analyzer.do_basic_analyze()
foil_arcs = do_foil_must_be_feasible(solver)
counter = TrackedCounter(start=0, step=1)
root_info = solver.process_data_for_root_problem()

root = ProblemNode(solver, root_info, foil_arcs, solver.current_solution_map, solver.org_graph, None, counter, 0)
root.apply_modified_arc()

# Call handle_weight_with_recovery + create_network_graph like calc_sub_best
from src.utils.dataparser import handle_weight_with_recovery, create_network_graph
root.weight_df = handle_weight_with_recovery(root.map_df, c.user_model)
_, root.new_graph = create_network_graph(root.weight_df)

# Call get_route
path_best, G_path_best, df_path_best = solver.router.get_route(
    root.new_graph, solver.data_holder.start_node_lc, solver.data_holder.end_node_lc, solver.heuristic_f
)
print(f"df_path_best columns: {list(df_path_best.columns)}")
print(f"df_path_best has 'arc': {'arc' in df_path_best.columns}")
# Check if momepy.nx_to_gdf adds 'arc' column
# The graph edge data doesn't have 'arc', so df shouldn't either
# But correct_arc_direction needs it... does it crash?
try:
    from src.utils.common_utils import correct_arc_direction
    df_corrected = correct_arc_direction(df_path_best, solver.data_holder.start_node_id, solver.data_holder.end_node_id)
    print(f"correct_arc_direction succeeded! Columns: {list(df_corrected.columns)}")
except Exception as e:
    print(f"correct_arc_direction FAILED: {e}")
