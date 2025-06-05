import pandas as pd
import matplotlib.pyplot as plt
import os

# Directory and file setup
input_dir = "Results/Logs"
output_dir = "Results/Graphs"
os.makedirs(output_dir, exist_ok=True)
files = [f"server_h{i}_cleaned.csv" for i in range(5, 9)]

# Manual color choices for better contrast
colors = ['blue', 'green', 'purple', 'red']

# Load and process data
combined_data = []
loss_averages = {}
for fname in files:
    path = os.path.join(input_dir, fname)
    if not os.path.exists(path):
        continue
    df = pd.read_csv(path, header=None)
    df.columns = ['timestamp', 'local_ip', 'local_port', 'remote_ip', 'remote_port', 'stream_id',
                  'interval', 'bytes', 'bandwidth_bps', 'jitter_ms', 'lost', 'total', 'loss_pct', 'ooo']

    # Filter and compute
    df = df[df['interval'].str.contains('-') & df['loss_pct'].notnull()]
    df[['start', 'end']] = df['interval'].str.split('-', expand=True).astype(float)
    df['bandwidth_mbps'] = df['bandwidth_bps'] / 1e6
    df['loss'] = df['loss_pct'].astype(float) / 100
    df['demanded_mbps'] = df['bandwidth_mbps'] * (1 + df['loss'])
    df['time'] = df['start']
    df['source_file'] = fname

    loss_averages[fname] = df['loss_pct'].astype(float).mean()
    combined_data.append(df[['time', 'bandwidth_mbps', 'demanded_mbps', 'source_file']])

# Combine all
if combined_data:
    all_data = pd.concat(combined_data)

    plt.figure(figsize=(12, 6))

    host_map = {
        "server_h5_cleaned.csv": "H1",
        "server_h6_cleaned.csv": "H2",
        "server_h7_cleaned.csv": "H3",
        "server_h8_cleaned.csv": "H4",
    }

    for i, (key, grp) in enumerate(all_data.groupby('source_file')):
        host = host_map.get(key, key)
        loss_avg = loss_averages.get(key, 0)
        color = colors[i % len(colors)]
        label_actual = f"{host} Actual BW ({loss_avg:.1f}% loss)"
        label_demanded = f"{host} Demanded BW"
        plt.plot(grp['time'], grp['demanded_mbps'], label=label_demanded, color=color, linestyle='--', alpha=0.6)
        plt.plot(grp['time'], grp['bandwidth_mbps'], label=label_actual, color=color, linestyle='-')

    plt.xlabel("Time (s)")
    plt.ylabel("Bandwidth (Mbps)")
    plt.title("Actual vs Demanded Bandwidth Over Time")
    plt.legend(loc='center left', bbox_to_anchor=(1.0, 0.5))
    plt.grid(True)
    plt.tight_layout()

    plot_path = os.path.join(output_dir, "bandwidth_used_vs_demanded_with_loss.png")
    plt.savefig(plot_path)
    plot_path
else:
    "No valid data to plot."
