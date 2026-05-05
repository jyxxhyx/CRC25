import sys,os,yaml,time
sys.path.insert(0,'.')
with open('config.yaml','r',encoding='utf-8') as f: yc=yaml.safe_load(f)
yc['paths']['route_name']='nwmkt_t_1_3'
from config import Config; c=Config(yc,base_dir='.'); c.load_from_yaml()
from src.solver.BaseSolver import BaseSolver
from src.AlgoTimer import AlgoTimer
t=AlgoTimer(time.time()); s=BaseSolver(c,t); s.init_from_config()
ipm=s.data_holder.id_point_map; G=s.org_graph
ipm_vals=set(ipm.values()); gn=set(G.nodes())
print(f'Overlap: {len(ipm_vals & gn)} / ipm={len(ipm_vals)} graph={len(gn)}')
u,v,k=list(G.edges(keys=True))[0]
d=G[u][v][k]
print(f'Edge sample keys: {sorted(d.keys())[:10]}')
print(f'arc attr: {d.get("arc")}')
# Check if arc (from map_df row) has 'arc' in graph edge
found=0
for idx,row in s.org_map_df.head(50).iterrows():
    i,j=row['arc']
    u_coord,v_coord=ipm[i],ipm[j]
    if G.has_edge(u_coord,v_coord):
        found+=1
    elif G.has_edge(v_coord,u_coord):
        found+=1
print(f'Found arcs in graph: {found}/50')
