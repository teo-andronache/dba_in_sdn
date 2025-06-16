#!/usr/bin/env python3
import re
import os
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.ticker as ticker

# ——— 1. Parse meter allocations from ryu.log ———
times = []
meters = {1: [], 2: [], 3: [], 4: []}
with open('ryu.log') as f:
    for line in f:
        m = re.match(
            r'>>> t=(\d+\.\d+) s; Pushed new meters: '
            r'\{1: ([\d\.]+), 2: ([\d\.]+), 3: ([\d\.]+), 4: ([\d\.]+)\}',
            line
        )
        if not m:
            continue
        t = float(m.group(1))
        times.append(t)
        for i in range(1, 5):
            # convert from kbps → Mbps
            meters[i].append(float(m.group(i + 1)) / 1000.0)

# ——— 2. Load and process server CSVs ———
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
    # split interval "X-Y"
    df[['start','end']] = (
        df['interval']
          .str.split('-', expand=True)
          .astype(float)
    )
    df['bw_mbps']  = df['bw_bps']   / 1e6
    df['loss']     = df['loss_pct'].astype(float) / 100.0
    df['demand']   = df['bw_mbps'] * (1 + df['loss'])
    df['time']     = df['start']
    dfs[host] = df

# ——— 3. Build per-host demanded & actual pivot tables ———
all_dem = []
all_act = []
for host, df in dfs.items():
    all_dem.append(df[['time','demand']].assign(host=host))
    all_act.append(df[['time','bw_mbps']].assign(host=host))

pivot_dem = (
    pd.concat(all_dem)
      .pivot_table(index='time', columns='host', values='demand', aggfunc='sum')
      .ffill()
)
pivot_act = (
    pd.concat(all_act)
      .pivot_table(index='time', columns='host', values='bw_mbps', aggfunc='sum')
      .ffill()
)

# find end of traffic so we can trim meters
max_time = max(pivot_act.index.max(), pivot_dem.index.max())

# ——— 4. Compute average loss between meter‐rate and demanded for labels ———
# ——— recompute per‐host loss by doing a proper merge_asof, clamping negative drops ———
loss_pct = {}
for i, host in enumerate(['H1','H2','H3','H4'], start=1):
    # 1) build two time‐series: one for demand, one for meter
    ser_dem = pivot_dem[host].rename("demand")
    ser_met = pd.Series(meters[i], index=times).rename("meter")

    # 2) merge_asof: only keep rows where both demand & meter are within POLL window
    df = pd.merge_asof(
        ser_dem.reset_index(),
        ser_met.reset_index(),
        left_on="time", right_on="index",
        direction="nearest",
        tolerance=0.5  # half‐second tolerance: adjust to your poll‐interval/clock skew
    ).dropna()

    # 3) compute loss ONLY when demanded > meter, clamp negative to zero
    df["gap"] = (df["demand"] - df["meter"]).clip(lower=0.0)
    df["loss_frac"] = df["gap"] / df["demand"]

    if len(df):
        loss_pct[host] = 100 * df["loss_frac"].mean()
    else:
        loss_pct[host] = 0.0

# now loss_pct['H1'] will be exactly 0.0 if your meter always met-or-exceeded H1’s demand

# ——— 5. Plot everything ———
fig, ax = plt.subplots(figsize=(12, 6))
colors = {'H1':'blue','H2':'green','H3':'purple','H4':'red'}

# a) per-host demanded (solid)
for host, color in colors.items():
    ax.plot(
        pivot_dem.index, pivot_dem[host],
        linestyle='-', color=color, alpha=0.8,
        label=f"{host} Demand ({loss_pct[host]:.1f}% loss)"
    )

# b) total demanded
total_dem = pivot_dem.sum(axis=1)
avg_dem = total_dem.mean()                        
ax.plot(
    total_dem.index, total_dem.values,
    linestyle='-', color='grey', linewidth=2,
    label=f"Aggregate Demand (avg {avg_dem:.1f} Mbps)" 
)


# c) total actual
total_act = pivot_act.sum(axis=1)
avg_act = total_act.mean()                          
ax.plot(
    total_act.index, total_act.values,
    linestyle='-', color='black', linewidth=2.5,
    label=f"Aggregate Thrpt (avg {avg_act:.1f} Mbps)" 
)

# d) meter rates (dashed), trimmed after traffic ends
trim_mask = np.array(times) <= max_time
for i, host in enumerate(['H1','H2','H3','H4'], start=1):
    t_trim = np.array(times)[trim_mask]
    m_trim = np.array(meters[i])[trim_mask]
    ax.plot(
        t_trim, m_trim,
        linestyle='--', color=colors[host], linewidth=1.5,
        label=f"{host} Meter"
    )

# styling
ax.set_xlabel("Time (s)")
ax.set_ylabel("Bandwidth (Mbps)")
ax.set_title("Per-Host Demanded Bandwidth vs. Meter Rates & Aggregate Actual/Demanded Bandwidth Over Time")

ax.yaxis.set_major_locator(ticker.MultipleLocator(5))
ax.yaxis.set_minor_locator(ticker.MultipleLocator(1))
ax.grid(which='major', linestyle='-', alpha=0.3)
ax.grid(which='minor', linestyle='--', alpha=0.1)

ax.legend(bbox_to_anchor=(1.02, 1), loc='upper left')
fig.tight_layout()

# ——— 6. Save final image ———
out_dir = "Results/Graphs"
os.makedirs(out_dir, exist_ok=True)
out_path = os.path.join(out_dir, "bandwidth_meters_and_actual.png")
fig.savefig(out_path, dpi=150)
print(f"Saved plot to {out_path}")
