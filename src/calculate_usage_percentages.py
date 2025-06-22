#!/usr/bin/env python3
import sys
import pandas as pd

def main():
    # Use provided CSV path or default to 'ryu_stats.csv'
    csv_path = sys.argv[1] if len(sys.argv) > 1 else "ryu_stats.csv"

    # Read the CSV into a DataFrame
    df = pd.read_csv(csv_path)

    # Compute averages
    avg_cpu = df['cpu_percent'].mean()
    avg_rss = df['rss_mb'].mean()
    avg_vms = df['vms_mb'].mean()

    # Print results
    print(f"Average CPU utilization: {avg_cpu:.2f}%")
    print(f"Average RSS memory usage: {avg_rss:.2f} MiB")
    print(f"Average VMS memory usage: {avg_vms:.2f} MiB")

if __name__ == "__main__":
    main()

