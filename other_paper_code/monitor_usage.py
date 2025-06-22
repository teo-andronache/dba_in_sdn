#!/usr/bin/env python3
import argparse
import csv
import subprocess
import sys
import time

try:
    import psutil
except ImportError:
    print("psutil not found; please install with `python3 -m pip install --user psutil`", file=sys.stderr)
    sys.exit(1)

def find_ryu_pid():
    # run ps aux and grep for ryu-manager, skip the grep process itself
    p = subprocess.Popen(["ps", "aux"], stdout=subprocess.PIPE, text=True)
    out, _ = p.communicate()
    for line in out.splitlines():
        if "ryu-manager" in line and "grep" not in line:
            parts = line.split()
            pid = parts[1]
            return int(pid)
    raise RuntimeError("Could not find ryu-manager process in ps aux")

def monitor(pid, interval, writer):
    p = psutil.Process(pid)
    writer.writerow(["timestamp","cpu_percent","rss_mb","vms_mb"])
    try:
        while True:
            cpu = p.cpu_percent(interval=None)  # non-blocking
            mem = p.memory_info()
            writer.writerow([
                time.time(),
                cpu,
                mem.rss / 1024**2,
                mem.vms / 1024**2
            ])
            sys.stdout.flush()
            time.sleep(interval)
    except psutil.NoSuchProcess:
        print(f"Process {pid} exited, stopping monitor.")
    except KeyboardInterrupt:
        pass

def main():
    parser = argparse.ArgumentParser(description="Monitor CPU/mem of ryu-manager")
    parser.add_argument("--auto", action="store_true",
                        help="auto-detect ryu-manager PID via ps")
    parser.add_argument("--pid", type=int,
                        help="PID to monitor (skip --auto)")
    parser.add_argument("--interval", type=float, default=1.0,
                        help="sampling interval in seconds")
    parser.add_argument("--output", required=True,
                        help="CSV file to write samples into")
    args = parser.parse_args()

    if args.auto:
        pid = find_ryu_pid()
        print(f"Auto-detected ryu-manager PID = {pid}")
    elif args.pid:
        pid = args.pid
    else:
        print("Either --auto or --pid must be specified", file=sys.stderr)
        sys.exit(1)

    with open(args.output, "w", newline="") as f:
        writer = csv.writer(f)
        monitor(pid, args.interval, writer)

if __name__ == "__main__":
    main()
