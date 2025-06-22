import pandas as pd
import os
from glob import glob

# --- 1) load & label each host's CSV ---
# assume files named: server_h5_cleaned.csv, ... h8
files = {
    "H1": "Results/Logs/server_h5_cleaned.csv",
    "H2": "Results/Logs/server_h6_cleaned.csv",
    "H3": "Results/Logs/server_h7_cleaned.csv",
    "H4": "Results/Logs/server_h8_cleaned.csv",
}

dfs = {}
for host, path in files.items():
    df = pd.read_csv(path, header=None)
    df.columns = [
        "ts","l_ip","l_pt","r_ip","r_pt","stream","interval",
        "bytes","bw_bps","jitter","lost","total","loss_pct","ooo"
    ]
    # extract start of interval (as float seconds) and compute Mbps
    df[["start","end"]] = df["interval"].str.split("-", expand=True).astype(float)
    df = df.set_index("start")
    df[f"{host}_Mbps"] = df["bw_bps"] / 1e6
    dfs[host] = df[[f"{host}_Mbps"]]

# --- 2) merge all into one time‐indexed DataFrame ---
merged = pd.concat(dfs.values(), axis=1).ffill().dropna()

# --- 3) define initial weight vector (in Mbps) and normalize ---
weights = {"H1":50, "H2":30, "H3":15, "H4":5}

# build y_i = x_i / w_i
for host in weights:
    merged[f"{host}_y"] = merged[f"{host}_Mbps"] / weights[host]

# --- 4) compute per‐interval weighted Jain ---
y_cols = [f"{h}_y" for h in weights]
num = merged[y_cols].sum(axis=1) ** 2
den = len(y_cols) * (merged[y_cols]**2).sum(axis=1)
merged["J_weighted"] = num / den

# --- 5) summary statistics ---
print("Mean weighted Jain fairness over run: ",
      merged["J_weighted"].mean())
