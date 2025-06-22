#!/usr/bin/env python3
import re
import time

def jain(xs):
    if not xs:
        return 0.0
    s, ss = sum(xs), sum(x * x for x in xs)
    return (s * s) / (len(xs) * ss) if ss else 0.0


def run_video_overload(net, pairs, duration=10):
    """
    For each (src, dst) in `pairs` (assumed len==8, h1-h8 → h9-h16) start
    **three** video streams (UDP @ 5 Mb/s) on consecutive ports 6000+.

    Prints per-flow rate / jitter / loss and a summary at the end.
    """
    print('*** TEST: 3 Video UDP streams per source ***')

    csv_re = re.compile(
        r'(?P<ts>[^,]+),[^,]+,[^,]+,[^,]+,[^,]+,\d,'
        r'[^,]+,(?P<bytes>\d+),(?P<bps>\d+),(?P<jit>[\d\.]+),'
        r'(?P<lost>\d+),(?P<tot>\d+)'
    )

    # stats collectors
    rates_by_src = {src: [] for src, _ in pairs}
    jitters, losses = [], []

    base_port = 6000
    servers = []

    # --- 1. start all servers -------------------------------------------------
    for _, dst in pairs:
        dst_h = net.get(dst)
        for i in range(3):
            servers.append(dst_h.popen(
                f'iperf -u -s -i 1 -y C -p {base_port + i}'
            ))
        base_port += 3

    time.sleep(1)

    # --- 2. start all clients -------------------------------------------------
    base_port = 6000
    procs = []
    start = time.time()

    for src, dst in pairs:
        cli, dst_h = net.get(src), net.get(dst)
        for i in range(3):
            port = base_port + i
            cmd  = (f'iperf -u -b 5m -c {dst_h.IP()} '
                    f'-p {port} -t {duration} -y C')
            procs.append((src, cli.popen(cmd), start))
        base_port += 3

    print('\n--- Flow results ---')

    for src, proc, t0 in procs:
        out, _ = proc.communicate()
        line = next((l for l in reversed(out.decode().splitlines())
                     if l.startswith('2025')), '')
        m = csv_re.match(line)
        if not m:
            continue

        rate   = float(m['bps']) / 1e6
        jitter = float(m['jit'])
        lost   = int(m['lost'])
        total  = int(m['tot'])
        loss   = 100.0 * lost / total if total else 0.0

        print(f'{src:<3} [video] rate={rate:6.2f} Mb/s ; jitter={jitter:5.2f} ms ; loss={loss:6.2f}% ;')

        rates_by_src[src].append(rate)
        jitters.append(jitter)
        losses.append(loss)

    for p in servers:
        p.terminate()

    # --- 3. summary -----------------------------------------------------------
    print('\n=== SUMMARY ===')
    all_rates = [r for rs in rates_by_src.values() for r in rs]
    total = sum(all_rates)
    print(f'Overall avg throughput  = {total/len(all_rates):.2f} Mb/s')
    print(f'Total throughput        = {total:.2f} Mbps')
    print(f'Avg jitter              = {sum(jitters)/len(jitters):.2f} ms')
    print(f'Avg loss                = {sum(losses)/len(losses):.2f} %')
    print(f'Fairness (Jain)         = {jain(all_rates):.3f}')