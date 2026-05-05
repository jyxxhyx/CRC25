"""Test fast_graph correctness by comparing slow and fast paths."""
import sys, os, yaml, time
sys.path.insert(0, '.')

from config import Config
with open('config.yaml', 'r', encoding='utf-8') as f:
    yc = yaml.safe_load(f)
yc['paths']['route_name'] = 'nwmkt_t_1_3'

c = Config(yc, base_dir='.')
c.load_from_yaml()

from src.solver.BaseSolver import BaseSolver
from src.AlgoTimer import AlgoTimer
from src.solver.ProblemNode import ProblemNode
from src.TrackedCounter import TrackedCounter
from src.solver.Operator import do_foil_must_be_feasible

# Build root problem
timer = AlgoTimer(time.time())
from src.solver.SearchSolver import SearchSolver
solver = SearchSolver(c, timer)
solver.init_from_config()
solver.analyzer.do_basic_analyze()
foil_arcs = do_foil_must_be_feasible(solver)
counter = TrackedCounter(start=0, step=1)
root_info = solver.process_data_for_root_problem()

# SLOW path
root = ProblemNode(solver, root_info, foil_arcs, solver.current_solution_map, solver.org_graph, None, counter, 0)
root.apply_modified_arc()
t0 = time.time()
root.calc_sub_best()
slow_time = time.time() - t0
slow_ge = root.graph_error
slow_re = root.route_error

print(f"SLOW: ge={slow_ge}, re={slow_re:.4f}, time={slow_time*1000:.0f}ms")
print(f"  best path nodes: {len(root.path_best) if root.path_best else 'None'}")

# Now test FAST path
from src.solver.fast_graph import fast_calc_sub_best
root2 = ProblemNode(solver, root_info, foil_arcs, solver.current_solution_map, solver.org_graph, None, counter, 0)
root2.apply_modified_arc()
t0 = time.time()
fast_calc_sub_best(root2)
fast_time = time.time() - t0
fast_ge = root2.graph_error
# Need to calc_error separately
root2.calc_error()

print(f"FAST: ge={root2.graph_error}, re={root2.route_error:.4f}, time={fast_time*1000:.0f}ms")
print(f"  best path nodes: {len(root2.path_best) if root2.path_best else 'None'}")
print(f"\nSpeedup: {slow_time/fast_time:.1f}x")
print(f"Same result: {root.graph_error == root2.graph_error}")
