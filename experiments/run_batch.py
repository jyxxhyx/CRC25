#!/usr/bin/env python3
"""Batch runner for CRC25 SearchSolver — writes results incrementally to JSONL."""
import os, sys, json, time, yaml

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = os.path.dirname(BASE_DIR)
sys.path.insert(0, PROJECT_DIR)
sys.path.insert(0, BASE_DIR)
os.chdir(PROJECT_DIR)

from config import Config
from src.solver.SearchSolver import SearchSolver
from src.AlgoTimer import AlgoTimer
from src.utils.common_utils import set_seed
from logger_config import logger

import logging
logging.getLogger().setLevel(logging.WARNING)

def get_route_names():
    """Get all test route names."""
    routes_path = os.path.join(PROJECT_DIR, "data", "test", "osdpm")
    return sorted(os.listdir(routes_path))

def solve_instance(route_name, time_limit=120, routes_path=None, maps_path=None):
    """Solve a single instance with given time limit. Returns dict or None."""
    AlgoTimer.time_limit = time_limit
    timer = AlgoTimer(time.time())
    set_seed()

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

    solver = SearchSolver(config, timer)
    solver.init_from_config()

    try:
        solver.do_solve()
        solver.process_solution_from_model()

        re = float(solver.route_error)
        ge = int(solver.graph_error)
        feasible = re <= 0.05  # threshold from metadata

        return {
            "route": route_name,
            "graph_error": ge,
            "route_error": round(re, 6),
            "feasible": feasible,
            "time": round(time.time() - timer.start_time, 1),
            "best_node": str(solver.best_leaf_node) if solver.best_leaf_node else None,
        }
    except Exception as e:
        elapsed = round(time.time() - timer.start_time, 1)
        return {
            "route": route_name,
            "graph_error": None,
            "route_error": None,
            "feasible": False,
            "time": elapsed,
            "error": str(e),
        }

def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("time_limit", type=int, help="time limit per instance (seconds)")
    parser.add_argument("output", help="output JSONL file path")
    parser.add_argument("--routes", nargs="*", default=None, help="specific routes (default: all in routes-dir)")
    parser.add_argument("--routes-dir", default=None, help="directory containing route subdirs (default: data/test/osdpm)")
    args = parser.parse_args()

    routes = args.routes or get_route_names()
    out_path = os.path.join(PROJECT_DIR, args.output)
    routes_path = args.routes_dir
    maps_path = None
    # Auto-detect maps_path for train
    if routes_path and 'train' in routes_path:
        maps_path = 'data/train/maps'

    # Skip already completed routes
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
        print(f">>> {route_name} (time_limit={args.time_limit}s) ...", flush=True)
        result = solve_instance(route_name, args.time_limit, routes_path=routes_path, maps_path=maps_path)
        print(f"  {'OK' if result['feasible'] else 'NO'} ge={result['graph_error']} ({result['time']}s)", flush=True)

        # Incremental write
        with open(out_path, "a") as f:
            f.write(json.dumps(result) + "\n")
        results.append(result)

    # Summary
    feasible = [r for r in results if r["feasible"]]
    total_ge = sum(r["graph_error"] for r in feasible if r["graph_error"] is not None)
    print(f"\n{'='*70}")
    print(f"  {len(feasible)}/{len(results)} feasible, total_ge={total_ge}")
    print(f"{'='*70}")

if __name__ == "__main__":
    main()
