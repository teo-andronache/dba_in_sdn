import os
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.ticker as ticker

# ——— CONFIG ———
INPUT_DIR  = "Results/Logs"
OUTPUT_DIR = "Results/Graphs"
os.makedirs(OUTPUT_DIR, exist_ok=True)

files = [f"server_h{i}_normalized.csv" for i in (5,6,7,8)]
host_map = {
    "server_h5_normalized.csv": "H1",
    "server_h6_normalized.csv": "H2",
    "server_h7_normalized.csv": "H3",
    "server_h8_normalized.csv": "H4",
}
colors = ['blue','green','purple','red']

# ——— LOAD & TAG ———
dfs = []
loss_avg = {}
for fn in files:
    path = os.path.join(INPUT_DIR, fn)
    if not os.path.exists(path):
        continue

    df = pd.read_csv(path)   # columns: time, actual_mbps, demanded_mbps, loss_pct
    host = host_map[fn]
    df['host'] = host
    loss_avg[host] = df['loss_pct'].mean()
    dfs.append(df)

all_df = pd.concat(dfs, ignore_index=True)

# ——— PIVOT ———
pivot_act = all_df.pivot_table(
    index='time', columns='host', values='actual_mbps', aggfunc='sum'
).sort_index()
pivot_dem = all_df.pivot_table(
    index='time', columns='host', values='demanded_mbps', aggfunc='sum'
).sort_index()

# ——— PLOT ———
fig, ax = plt.subplots(figsize=(12,6))

for (host, color) in zip(pivot_act.columns, colors):
    ax.plot(
        pivot_dem.index, pivot_dem[host],
        linestyle='--', alpha=0.6, color=color,
        label=f"{host} Demanded ({loss_avg[host]:.1f}% loss)"
    )
    ax.plot(
        pivot_act.index, pivot_act[host],
        linestyle='-', color=color,
        label=f"{host} Actual"
    )

# total
total = pivot_act.sum(axis=1)
ax.plot(
    total.index, total.values,
    color='black', linewidth=2.5,
    label='Total Actual Throughput'
)

# formatting
ax.set(
    xlabel="Time (s)",
    ylabel="Bandwidth (Mbps)",
    title="Normalized 1 s-interval Bandwidth per Host and Total"
)
ax.yaxis.set_major_locator(ticker.MultipleLocator(5))
ax.yaxis.set_minor_locator(ticker.MultipleLocator(1))
ax.grid(which='major', linestyle='-', alpha=0.3)
ax.grid(which='minor', linestyle='--', alpha=0.1)
ax.legend(bbox_to_anchor=(1.02,1), loc='upper left')

fig.tight_layout()
out_png = os.path.join(OUTPUT_DIR, "normalized_linear_plot.png")
fig.savefig(out_png, dpi=150)
print(f"Saved plot to {out_png}")
