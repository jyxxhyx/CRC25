# CRC25 for_submission Branch — Autoresearch Plan

## Baseline Status
- Code: for_submission branch, SearchSolver with PriorityQueue BFS
- Time limit: 120s/instance
- Baseline running...

## Code Architecture (Key Findings)

### 1. Search Loop (SearchSolver.do_solve)
- PriorityQueue with `__lt__` = `(route_error, level, graph_error)` → BFS tendency
- Only picks first fork-merge pair: `values()[0]`
- Pruning: only prunes infeasible nodes worse than current best feasible
- No max_depth limit (relies on time_over_check)

### 2. Node Expansion (ProblemNode)
- `deepcopy(map_df)` every node — GeoDataFrame deepcopy is expensive
- `calc_sub_best()`: rebuilds weight_df + graph + Dijkstra per node
- `calc_error()`: computes virtual_op_list (diff with original) per node

### 3. Arc Scoring (Operator)
- 4 features: degree_centrality, edge_bc, alt_ratio, fork_merge random
- Weights: deg=0.15, bc=0.35, alt_ratio=0.45, rand=0.05
- `adaptive_node_expansion`: level<3 → 4, 3-6 → 2, >6 → 1

### 4. Edge BC Calculation
- `edge_betweenness_to_target_multigraph`: single-target exact BC (good!)
- Called per expansion — expensive for large graphs

### 5. Key Bottlenecks
1. **deepcopy(map_df)** — O(n) per node, GeoDataFrame heavy
2. **calculate_alt_ratio** — Dijkstra per candidate arc per expansion
3. **edge_betweenness** — exact BC per expansion
4. **Only first fork-merge** — ignores other divergence points
5. **BFS ordering** — explores many shallow nodes, may miss deep fixes

## Optimization Strategy (20 Rounds)

### Phase 1: Performance (rounds 1-5)
- [x] exp1: Replace deepcopy with copy-on-write (track diffs only)
- [x] exp2: Approximate BC (sampling k endpoints)
- [x] exp3: Cache/skip alt_ratio computation
- [x] exp4: Increase time_limit to 240s

### Phase 2: Search Strategy (rounds 6-12)
- [ ] exp5: DFS ordering `(-level, re, ge)` instead of BFS `(re, level, ge)`
- [ ] exp6: Process ALL fork-merge pairs, not just first
- [ ] exp7: Adaptive branch count (more at root, less deep)
- [ ] exp8: Max depth limit with fallback to best-so-far
- [ ] exp9: Multi-restart from different initial modifications

### Phase 3: Scoring (rounds 13-17)
- [ ] exp10: Tune feature weights (grid search on train)
- [ ] exp11: Add route_overlap feature
- [ ] exp12: Use modified arcs from previous iterations
- [ ] exp13: Batch arc modifications (modify 2+ arcs per node)

### Phase 4: Integration (rounds 18-20)
- [ ] exp18: Best combination of above
- [ ] exp19: Final tuning on test set
- [ ] exp20: Ablation experiment

## Metrics
- Primary: total_graph_error (lower better)
- Secondary: feasible_count (40/40 target)
- Tertiary: avg_time_per_instance
