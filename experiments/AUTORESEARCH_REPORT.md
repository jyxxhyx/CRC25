# CRC25 Autoresearch Report

## Branch: `autoresearch/optimize` (based on `for_submission`)

## Final Result: Hybrid (MIP + SearchSolver with Exp8 optimizations)

| 指标 | Baseline | Exp8 (纯Search) | Hybrid (MIP+Search) | 总改善 |
|------|----------|----------------|---------------------|--------|
| Train feasible | 25/25 | 25/25 | 25/25 | = |
| Train ge | 69 | 58 | **55** | **-20%** |
| Test feasible | 38/40 | 40/40 | **40/40** | **+2** |
| Test ge | 126 | 121 | **109** | **-14%** |

## 实验总览

### Phase A: SearchSolver 优化 (Exp0-12)

| Exp | 改动 | Train ge | Test fea | Test ge | 结论 |
|-----|------|----------|----------|---------|------|
| 0 | Baseline | 69 | 38/40 | 126 | 基准 |
| 1 | DFS 优先级 | 72 | 40/40 | 153 | 负面 |
| 2 | 所有 fork-merge pairs | 59 | 40/40 | 125 | 正面 |
| 3 | +快速图构建 | 59 | 40/40 | 122 | 正面 |
| 4 | 240s/实例 | ~59 | — | — | 中性 |
| 5 | 加强剪枝 | — | 丢可行解 | — | 负面 |
| 6 | 权重调优 | — | 丢可行解 | — | 负面 |
| 7 | +BC 去重 | 59 | 40/40 | 121 | 正面 |
| 8 | +自适应分支(8/6/2/1) | **58** | **40/40** | **121** | 最优 |
| 9 | 展开可行解节点 | 7x变慢 | — | — | 负面 |
| 10 | 更激进分支(10/6/2/1) | 更差 | — | — | 负面 |
| 11 | CHANGE 混合策略 | 58 | 太慢 | — | 负面 |
| 12 | 去掉 alt_ratio | 63 | — | — | 负面 |

### Phase B: 消融实验 (在 Exp8 基础上逐一去掉)

| Ablation | 去掉的组件 | Train ge | 贡献 (ge) |
|----------|-----------|----------|-----------|
| 1 | 多 fork-merge pairs | 68 | **+10** |
| 3 | 自适应分支 (恢复原始 6/4/2/1) | 59 | **+1** |
| 4 | BC 去重 | 58 | 0 (性能优化) |
| — | 快速图构建 | — | 0 (性能优化) |
| exp12 | alt_ratio (用边长度替代) | 63 | **+5** |

### Phase C: Hybrid (MIP 提示 + SearchSolver)

| 方法 | Train ge | Test fea | Test ge |
|------|----------|----------|---------|
| Exp8 (纯 Search) | 58 | 40/40 | 121 |
| **Hybrid (MIP→Search)** | **55** | **40/40** | **109** |
| MIP 贡献 | **-3** | = | **-12** |

**MIP 机制**：
1. MIP 用 scipy linprog (HiGHS) 解 mixed-integer LP，找到全局最优的 arc 修改方案
2. MIP 的 modify_arc_solution 传入 SearchSolver 的 modify_arc_dict
3. Operator 给 MIP 建议的 arc 加 1.5x 评分加成（from_mip 特征，权重 0.35）
4. 如果 MIP 建议 CHANGE (path_type swap)，搜索时也用 CHANGE 而非 TO_INFE
5. SearchSolver 在 MIP 提示引导下搜索方向更精准

**MIP 开销**：平均 6-13s/实例，留给搜索的时间仍充足

**MIP 逐实例对比**（hybrid ge - exp8 ge，负数 = hybrid 更优）：

训练集（25 实例）：

| Route | exp8 | hybrid | diff |
|-------|------|--------|------|
| osdpm_4_1 | 8 | 5 | **-3** |
| 其余 24 个 | — | — | 0 |

测试集（40 实例）：

| Route | exp8 | hybrid | diff | 说明 |
|-------|------|--------|------|------|
| osdpm_t_0_4 | 11 | 5 | **-6** | 最大改善 |
| osdpm_t_0_3 | 8 | 6 | **-2** | |
| nwmkt_t_0_1 | 4 | 3 | **-1** | |
| nwmkt_t_0_2 | 7 | 6 | **-1** | |
| osdpm_t_2_3 | 6 | 5 | **-1** | |
| osdpm_t_4_3 | 4 | 3 | **-1** | |
| 其余 34 个 | — | — | 0 | |

**MIP 帮助的实例特征**：全是 osdpm 类型（6/6）或 nwmkt 大图，ge 较高（≥3），说明 MIP 在复杂实例上通过全局 LP 信息引导搜索方向，找到更优解。不帮助的实例 ge 本身已很低（1-2），优化空间有限。

## 各组件贡献总结

| 组件 | ge 贡献 | 类型 |
|------|---------|------|
| **多 fork-merge pairs** | **-10** | 搜索策略 |
| **MIP 提示** | **-3 train / -12 test** | 搜索引导 |
| **alt_ratio 特征** | **-5** | 评分特征 |
| **自适应分支 (8/6/2/1)** | **-1** | 搜索策略 |
| **快速图构建** | 0 (加速) | 性能优化 |
| **BC 去重** | 0 (加速) | 性能优化 |

## 关键发现

1. **多 pairs 是最大贡献者**（-10 ge）：处理所有 fork-merge pairs 而非只取第一个
2. **MIP 提示是第二贡献者**（-3 train / -11 test）：LP 全局信息引导搜索方向
3. **alt_ratio 不可替代**（-5 ge）：替代路径比率是最强特征
4. **搜索策略很脆弱**：权重、剪枝、DFS 任何偏离都导致丢可行解
5. **时间是最关键约束**：高 ge 实例都跑满 120s，更多时间 = 更优解
6. **性能优化间接贡献**：快速图构建 + BC 去重节省时间 → 更多节点探索 → 间接降低 ge
