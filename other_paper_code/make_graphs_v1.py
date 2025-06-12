import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.ticker as ticker
import os

# Directory and file setup
input_dir = "Results/Logs"
output_dir = "Results/Graphs"
os.makedirs(output_dir, exist_ok=True)
files = [f"server_h{i}_cleaned.csv" for i in range(5, 9)]

# Manual color choices for better contrast
colors = ['blue', 'green', 'purple', 'red']

# Host label mapping
host_map = {
    "server_h5_cleaned.csv": "H1",
    "server_h6_cleaned.csv": "H2",
    "server_h7_cleaned.csv": "H3",
    "server_h8_cleaned.csv": "H4",
}

# Load and process data
combined_data = []
loss_averages = {}
for fname in files:
    path = os.path.join(input_dir, fname)
    if not os.path.exists(path):
        continue
    df = pd.read_csv(path, header=None)
    df.columns = [
        'timestamp', 'local_ip', 'local_port', 'remote_ip', 'remote_port',
        'stream_id', 'interval', 'bytes', 'bandwidth_bps', 'jitter_ms',
        'lost', 'total', 'loss_pct', 'ooo'
    ]

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
if not combined_data:
    print("No valid data to plot.")
else:
    all_data = pd.concat(combined_data)

    # Pivot to get one column per host for actual and demanded
    pivot_actual = all_data.pivot_table(
        index='time',
        columns='source_file',
        values='bandwidth_mbps',
        aggfunc='sum'
    )
    pivot_demand = all_data.pivot_table(
        index='time',
        columns='source_file',
        values='demanded_mbps',
        aggfunc='sum'
    )

    # Fill forward missing values so the total line doesn't drop
    pivot_actual = pivot_actual.ffill()
    pivot_demand = pivot_demand.ffill()

    # Plotting
    fig, ax = plt.subplots(figsize=(12, 6))

    for (col, color) in zip(pivot_actual.columns, colors):
        host = host_map.get(col, col)
        loss_avg = loss_averages.get(col, 0)
        # Demanded (dashed)
        ax.plot(
            pivot_demand.index,
            pivot_demand[col],
            linestyle='--',
            alpha=0.6,
            color=color,
            label=f"{host} Demanded ({loss_avg:.1f}% loss)"
        )
        # Actual (solid)
        ax.plot(
            pivot_actual.index,
            pivot_actual[col],
            linestyle='-',
            color=color,
            label=f"{host} Actual"
        )

    # Total demanded throughput 
    total_demand = pivot_demand.sum(axis=1)
    ax.plot(
        total_demand.index,
        total_demand.values,
        color='grey',
        linestyle='-',
        linewidth=2,
        label='Total Demanded Throughput'
    )

    # Total actual throughput 
    total_actual = pivot_actual.sum(axis=1)
    ax.plot(
        total_actual.index,
        total_actual.values,
        color='black',
        linewidth=2.5,
        label='Total Actual Throughput'
    )

    # Y-axis granularity
    ax.yaxis.set_major_locator(ticker.MultipleLocator(5))
    ax.yaxis.set_minor_locator(ticker.MultipleLocator(1))
    ax.grid(which='major', linestyle='-', alpha=0.3)
    ax.grid(which='minor', linestyle='--', alpha=0.1)

    # Labels, title, legend
    ax.set(
        xlabel="Time (s)",
        ylabel="Bandwidth (Mbps)",
        title="Per-Host vs. Aggregate Bandwidth Utilization Over Time"
    )
    ax.legend(bbox_to_anchor=(1.02, 1), loc='upper left')

    fig.tight_layout()
    plot_path = os.path.join(output_dir, "bandwidth_utilization_per_host_and_total.png")
    fig.savefig(plot_path, dpi=150)
    print(f"Saved plot to {plot_path}")
