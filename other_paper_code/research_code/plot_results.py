import os, re
import pandas as pd
import matplotlib.pyplot as plt

LOG_DIR   = 'Results/Logs'
GRAPH_DIR = 'Results/Graphs'
os.makedirs(GRAPH_DIR, exist_ok=True)
FILES = [os.path.join(LOG_DIR, f'server_h{i}.txt') for i in range(5, 9)]

# ---------- regex ----------
conn_re = re.compile(r'\[\s*(\d+)]\s+local .* connected')
perf_re = re.compile(
    r'\[\s*(\d+)]\s+(\d+\.\d+)-\s*(\d+\.\d+) sec\s+[\d.]+\s*MBytes\s+([\d.]+)\s*Mbits/sec.*?(\d+)/\s*(\d+)'
)

def parse_server(path: str) -> pd.DataFrame:
    with open(path) as f:
        lines = f.readlines()

    starts = [i for i,l in enumerate(lines) if conn_re.search(l)]
    starts.append(len(lines))

    rows, offset = [], 0.0
    for s, e in zip(starts[:-1], starts[1:]):
        sess_id = conn_re.search(lines[s]).group(1)
        for ln in lines[s:e]:
            m = perf_re.search(ln)
            if m and m.group(1) == sess_id:
                t0, t1 = float(m.group(2)), float(m.group(3))
                if t1 - t0 > 1.5:          # ignore summary row 0.0-10.0
                    continue
                bw = float(m.group(4))
                lost, tot = map(int, (m.group(5), m.group(6)))
                loss_pct = lost / tot if tot else 0.0
                rows.append(
                    (offset + t0, bw, bw * (1 + loss_pct))
                )
                last_end = t1
        offset += last_end               # next session continues in time
    return pd.DataFrame(rows, columns=['Time','Actual','Demanded'])

# ---------- read all ----------
dfs=[]
for f in FILES:
    df = parse_server(f)
    if not df.empty:
        df['Server'] = os.path.basename(f)
        dfs.append(df)

# ---------- plot ----------
plt.figure(figsize=(12,6))
colors = plt.rcParams['axes.prop_cycle'].by_key()['color']

for i, df in enumerate(dfs):
    c = colors[i % len(colors)]
    tag = df['Server'].iat[0]
    plt.plot(df['Time'], df['Actual'],   label=f'{tag} – Actual',   color=c)
    plt.plot(df['Time'], df['Demanded'], '--',                    label=f'{tag} – Demanded',
             color=c, alpha=.55)

plt.xlabel('Time (s)')
plt.ylabel('Bandwidth (Mbits/sec)')
plt.title('Actual vs Demanded Bandwidth per Server')
plt.grid(True)
plt.legend()
out = os.path.join(GRAPH_DIR, 'bandwidth_clean.png')
plt.tight_layout(); plt.savefig(out); plt.close()
print(f'Graph saved → {out}')
