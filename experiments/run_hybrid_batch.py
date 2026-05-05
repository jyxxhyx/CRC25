#!/usr/bin/env python3
"""Hybrid batch runner: MIP first, then SearchSolver with MIP hints. Writes results to JSONL."""
import os, sys, json, time, yaml

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = os.path.dirname(BASE_DIR)
sys.path.insert(0, PROJECT_DIR)
sys.path.insert(0, BASE_DIR)
os.chdir(PROJECT_DIR)

from config import Config
from src.solver.MipSolver import MipSolver
from src.solver.SearchSolver import SearchSolver
from src.AlgoTimer import AlgoTimer
from src.utils.common_utils import set_seed

import logging
logging.getLogger().setLevel(logging.WARNING)

def solve_hybrid(route_name, time_limit=120, routes_path=None, maps_path=None):
    """Solve using hybrid: MIP → SearchSolver with MIP hints."""
    config_path = os.path.join(PROJECT_DIR, "config.yaml")
    with open(config_path, 'r', encoding='utf-8') as f:
        yaml_config = yaml.safe_load(f)
    yaml_config['paths']['route_name'] = route_name
    yaml_config['params']['visual'] = False
    if routes_path:
        yaml_config['paths']['routes_path'] = routes_path
    if maps_path:
        yaml_config['paths']['maps_path'] = maps_path

    config = Config(yaml_config, base_dir=PROJECT_DIR)
    config.load_from_yaml()

    # --- Phase 1: MIP ---
    mip_start = time.time()
    AlgoTimer.time_limit = time_limit
    timer = AlgoTimer(time.time())
    set_seed()

    mip_solver = MipSolver(config, timer)
    mip_solver.init_from_config()

    try:
        mip_solver.init_model()
        mip_solver.solve_model()
        mip_solver.process_solution_from_model()
        mip_cost = time.time() - mip_start
        mip_re = float(mip_solver.route_error)
        mip_ge = int(mip_solver.graph_error)
        mip_ok = True
    except Exception as e:
        mip_cost = time.time() - mip_start
        mip_re, mip_ge = float('inf'), float('inf')
        mip_ok = False

    # If MIP already optimal
    if mip_ok and mip_re <= 0 and mip_ge <= 1:
        return {
            "route": route_name,
            "graph_error": mip_ge,
            "route_error": round(mip_re, 6),
            "feasible": mip_re <= 0.05,
            "time": round(mip_cost, 1),
            "final": "mip",
            "mip_cost": round(mip_cost, 1),
            "search_cost": 0,
        }

    # --- Phase 2: SearchSolver with MIP hints ---
    remaining = time_limit - (time.time() - timer.start_time)
    if remaining < 5:
        # Not enough time for search
        if mip_ok:
            return {
                "route": route_name,
                "graph_error": mip_ge,
                "route_error": round(mip_re, 6),
                "feasible": mip_re <= 0.05,
                "time": round(time.time() - timer.start_time, 1),
                "final": "mip",
                "mip_cost": round(mip_cost, 1),
                "search_cost": 0,
            }
        else:
            return {
                "route": route_name,
                "graph_error": None,
                "route_error": None,
                "feasible": False,
                "time": round(time.time() - timer.start_time, 1),
                "error": "MIP failed + no time for search",
            }

    search_timer = AlgoTimer(time.time())
    search_solver = SearchSolver(config, search_timer)
    search_solver.init_from_other_solver(mip_solver)

    try:
        search_solver.do_solve()
        search_solver.process_solution_from_model()
        search_re = float(search_solver.route_error)
        search_ge = int(search_solver.graph_error)
        search_ok = True
    except Exception as e:
        search_re, search_ge = float('inf'), float('inf')
        search_ok = False

    search_cost = time.time() - search_timer.start_time

    # Compare: pick better result
    if mip_ok and (mip_re, mip_ge) <= (search_re if search_ok else float('inf'), search_ge if search_ok else float('inf')):
        final_re, final_ge, final_src = mip_re, mip_ge, "mip"
    elif search_ok:
        final_re, final_ge, final_src = search_re, search_ge, "search"
    elif mip_ok:
        final_re, final_ge, final_src = mip_re, mip_ge, "mip"
    else:
        return {
            "route": route_name,
            "graph_error": None,
            "route_error": None,
            "feasible": False,
            "time": round(time.time() - timer.start_time, 1),
            "error": "both MIP and search failed",
        }

    return {
        "route": route_name,
        "graph_error": final_ge,
        "route_error": round(final_re, 6),
        "feasible": final_re <= 0.05,
        "time": round(time.time() - timer.start_time, 1),
        "final": final_src,
        "mip_cost": round(mip_cost, 1),
        "search_cost": round(search_cost, 1),
    }

def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("time_limit", type=int)
    parser.add_argument("output")
    parser.add_argument("--routes", nargs="*", default=None)
    parser.add_argument("--routes-dir", default=None)
    args = parser.parse_args()

    routes_path = args.routes_dir
    if routes_path:
        full_routes_dir = os.path.join(PROJECT_DIR, routes_path)
        routes = args.routes or sorted(os.listdir(full_routes_dir))
    else:
        routes_path = 'data/test/osdpm'
        full_routes_dir = os.path.join(PROJECT_DIR, routes_path)
        routes = args.routes or sorted(os.listdir(full_routes_dir))

    out_path = os.path.join(PROJECT_DIR, args.output)
    maps_path = None
    if routes_path and 'train' in routes_path:
        maps_path = 'data/train/maps'

    # Skip completed
    completed = set()
    if os.path.exists(out_path):
        with open(out_path) as f:
            for line in f:
                if line.strip():
                    completed.add(json.loads(line)["route"])

    results = []
    for route_name in routes:
        if route_name in completed:
            continue
        print(f">>> {route_name} (hybrid, time_limit={args.time_limit}s) ...", flush=True)
        result = solve_hybrid(route_name, args.time_limit, routes_path=routes_path, maps_path=maps_path)
        src = result.get('final', '?')
        print(f"  {'OK' if result['feasible'] else 'NO'} ge={result['graph_error']} [{src}] ({result['time']}s, mip={result.get('mip_cost',0):.1f}s)", flush=True)

        with open(out_path, "a") as f:
            f.write(json.dumps(result) + "\n")
        results.append(result)

    feasible = [r for r in results if r["feasible"]]
    total_ge = sum(r["graph_error"] for r in feasible if r["graph_error"] is not None)
    mip_wins = sum(1 for r in results if r.get('final') == 'mip')
    search_wins = sum(1 for r in results if r.get('final') == 'search')
    print(f"\n{'='*70}")
    print(f"  {len(feasible)}/{len(results)} feasible, total_ge={total_ge}")
    print(f"  mip_wins={mip_wins}, search_wins={search_wins}")
    print(f"{'='*70}")

if __name__ == "__main__":
    main()
