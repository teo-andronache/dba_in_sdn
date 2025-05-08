import re
import time
import random
from collections import defaultdict

def run_traffic_mix_voip_video_bulk_bursty(net, pairs,
                     total_time=60.0,
                     avg_interval=0.5,
                     dur_range=(1,10),
                     base_port=7000):
    """
    Fire short bursts of three traffic types (VoIP, Video, Bulk) for total_time seconds:
      - Inter-arrival ~ Exp(1/avg_interval)
      - Durations uniform in dur_range (seconds)
      - VoIP: UDP @ 100 kbit/s
      - Video: UDP @ 5 Mbit/s
      - Bulk: TCP (no -u flag)
    Each burst picks a random (src,dst) pair from `pairs`, and a random type.
    """
     # regex to catch Kbits/sec or Mbits/sec
    pat = re.compile(r'([\d\.]+)\s+([KM]bits/sec)')

    # Prepare containers
    types = ['voip','video','bulk']
    class_rates = {t: [] for t in types}
    host_totals = defaultdict(float)

    # Launch bursts
    procs = []  # list of (src, ftype, popen, dur)
    start = time.time()
    i = 0
    while time.time() - start < total_time:
        src, dst = random.choice(pairs)
        ftype     = random.choice(types)
        dur       = random.uniform(*dur_range)
        port      = base_port + i

        # server flags
        srv_flag = '-u -s' if ftype in ('voip','video') else '-s'
        # client flags
        if   ftype == 'voip':  cli_flag = '-u -b 100k'
        elif ftype == 'video': cli_flag = '-u -b 5m'
        else:                   cli_flag = ''

        # start server
        net.get(dst).popen(f'iperf {srv_flag} -p {port}')
        # start client
        cmd = f'iperf {cli_flag} -c {net.get(dst).IP()} -p {port} -t {dur:.2f}'
        print(f"*** Burst {i}: {src}->{dst} [{ftype}] dur={dur:.2f}s port={port}")
        p = net.get(src).popen(cmd)

        procs.append((src, ftype, p, dur))
        i += 1
        time.sleep(random.expovariate(1/avg_interval))

    # Collect and parse results
    print("\n--- Burst Results ---")
    for src, ftype, p, dur in procs:
        out, _ = p.communicate()
        text = out.decode(errors='ignore')
        m = pat.search(text)
        rate = 0.0
        if m:
            val, unit = float(m.group(1)), m.group(2)
            rate = val/1000.0 if unit.startswith('K') else val
        print(f"{src} [{ftype}] = {rate:.2f} Mbit/s")
        class_rates[ftype].append(rate)
        host_totals[src] += rate

    # Tear down any leftover servers
    # (Note: iperf -s processes will exit when test ends)

    # 4) Summary statistics
    print('\n=== SUMMARY ===')
    # overall
    all_rates = [r for rates in class_rates.values() for r in rates]
    if all_rates:
        total   = sum(all_rates)
        avg     = total / len(all_rates)
        j_all   = (total**2) / (len(all_rates) * sum(r*r for r in all_rates))
        print(f'Overall average_throughput = {avg:.2f} Mbit/s')
        print(f'Overall total_throughput   = {total:.2f} Mbit/s')
        print(f'Overall fairness_index     = {j_all:.3f}')
    else:
        print('No bursts completed')

    # per-class
    for ftype in types:
        rates = class_rates[ftype]
        if rates:
            tot_c = sum(rates)
            j_c   = (tot_c**2) / (len(rates)*sum(r*r for r in rates))
            print(f'{ftype.capitalize()} fairness_index = {j_c:.3f}')
        else:
            print(f'No {ftype} bursts')

    # per-host
    host_rates = list(host_totals.values())
    if host_rates:
        tot_h = sum(host_rates)
        avg_h = tot_h / len(host_rates)
        j_h   = (tot_h**2) / (len(host_rates)*sum(r*r for r in host_rates))
        print(f'Host-level avg_throughput = {avg_h:.2f} Mbit/s')
        print(f'Host-level fairness_index = {j_h:.3f}')
    else:
        print('No host data')