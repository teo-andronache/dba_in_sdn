#!/usr/bin/env python3
import os
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.ticker as ticker

# ——— 1. Static meter rates (Mbps) ———
static_rates = {1: 50.0, 2: 30.0, 3: 15.0, 4: 5.0}

# ——— 2. Load server CSVs and compute per‐interval demand (Mbps) ———
input_dir = "Results/Logs"
files = {
    'server_h5_cleaned.csv': 'H1',
    'server_h6_cleaned.csv': 'H2',
    'server_h7_cleaned.csv': 'H3',
    'server_h8_cleaned.csv': 'H4',
}

dfs = {}
for fname, host in files.items():
    path = os.path.join(input_dir, fname)
    if not os.path.exists(path):
        continue
    df = pd.read_csv(path, header=None)
    df.columns = [
        'ts','l_ip','l_pt','r_ip','r_pt','stream','interval',
        'bytes','bw_bps','jitter','lost','total','loss_pct','ooo'
    ]
    # split “start–end” into floats
    df[['start','end']] = df['interval'].str.split('-', expand=True).astype(float)
    # convert measured bw to Mbps, then account for loss_pct to get offered demand
    df['bw_mbps'] = df['bw_bps'] / 1e6
    df['loss_frac'] = df['loss_pct'].astype(float) / 100.0
    df['demand'] = df['bw_mbps'] * (1 + df['loss_frac'])
    df['time'] = df['start']
    dfs[host] = df

# ——— 3. Build pivot tables of demand per‐host vs time ———
dem_list = []
for host, df in dfs.items():
    dem_list.append(df[['time','demand']].assign(host=host))

pivot_dem = (
    pd.concat(dem_list)
      .pivot_table(index='time', columns='host', values='demand', aggfunc='sum')
      .ffill()
)

# ——— 4. Compute per‐host loss% vs static meter & synthetic throughput ———
loss_pct = {}
throughput = pd.DataFrame(index=pivot_dem.index, columns=pivot_dem.columns)

for i, host in enumerate(['H1','H2','H3','H4'], start=1):
    sr = static_rates[i]
    dem = pivot_dem[host]
    # loss only when demand > static
    gap = (dem - sr).clip(lower=0.0)
    loss_pct[host] = 100 * (gap / dem).mean()
    # synthetic throughput = min(demand, static)
    throughput[host] = np.minimum(dem, sr)

# ——— 5. Aggregate series & compute averages ———
agg_demand = pivot_dem.sum(axis=1)
agg_through = throughput.sum(axis=1)
active = agg_demand > 0

avg_dem = agg_demand[active].mean()
avg_thr = agg_through[active].mean()

# ——— 6. Plot ———
fig, ax = plt.subplots(figsize=(12,6))
colors = {'H1':'blue','H2':'green','H3':'purple','H4':'red'}

# a) per‐host demand solid
for host, color in colors.items():
    ax.plot(
        pivot_dem.index, pivot_dem[host],
        '-', color=color, alpha=0.8,
        label=f"{host} Demand ({loss_pct[host]:.1f}% loss)"
    )

# b) aggregate demand
ax.plot(
    agg_demand.index, agg_demand.values,
    '-', color='grey', linewidth=2,
    label=f"Aggregate Demand (avg {avg_dem:.1f} Mbps)"
)

# c) aggregate synthetic throughput
ax.plot(
    agg_through.index, agg_through.values,
    '-', color='black', linewidth=2.5,
    label=f"Aggregate Thrpt (avg {avg_thr:.1f} Mbps)"
)

# d) static meter lines dashed
times = pivot_dem.index.values
for i, host in enumerate(['H1','H2','H3','H4'], start=1):
    ax.plot(
        times, [static_rates[i]]*len(times),
        '--', color=colors[host], linewidth=1.5,
        label=f"{host} Meter = {static_rates[i]:.0f} Mbps"
    )

# styling
ax.set_xlabel("Time (s)")
ax.set_ylabel("Bandwidth (Mbps)")
ax.set_title("Per-Host Demanded Bandwidth vs. Static Meter Rates & Aggregate Actual/Demanded Bandwidth Over Time")
ax.yaxis.set_major_locator(ticker.MultipleLocator(5))
ax.yaxis.set_minor_locator(ticker.MultipleLocator(1))
ax.grid(which='major', linestyle='-', alpha=0.3)
ax.grid(which='minor', linestyle='--', alpha=0.1)
ax.legend(bbox_to_anchor=(1.02,1), loc='upper left')
fig.tight_layout()

# ——— 7. Save ———
os.makedirs("Results/Graphs", exist_ok=True)
out_path = "Results/Graphs/static_qos_allocation.png"
fig.savefig(out_path, dpi=150)
print(f"Saved plot to", out_path)
