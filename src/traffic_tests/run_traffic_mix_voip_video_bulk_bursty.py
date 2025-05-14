import re
import time
import random
from collections import defaultdict

def jain(xs):
    """Jain's fairness index for a list of rates; returns 0 if no variation."""
    if not xs:
        return 0.0
    s = sum(xs)
    ss = sum(x*x for x in xs)
    if ss == 0.0:
        return 0.0
    return (s*s) / (len(xs) * ss)

def run_traffic_mix_voip_video_bulk_bursty(net, pairs,
                                           total_time=60.0,
                                           avg_interval=0.5,
                                           dur_range=(1,10),
                                           base_port=7000):
    """
    Fire bursts of three traffic types (VoIP, Video, Bulk):
      - total_time (s) - duration of the test
      - avg_interval (s) - average time between bursts
      - dur_range (s) - range of burst durations
      - VoIP: UDP @100kbps, Video: UDP @5Mbps, Bulk: TCP
    At the end we wait on all of them, clip overruns to total_time,
    parse CSV output, and compute per-burst + aggregate stats,
    plus overall average jitter & loss.
    """
    print('*** TEST: Bursty traffic mix VoIP/Video/Bulk***')
    print(f'Function parameters:')
    print(f"  - Average interval between bursts: avg_interval = {avg_interval:.2f}s")
    print(f"  - Range of duration for bursts: dur_range = {dur_range[0]:.2f} - {dur_range[1]:.2f}s")

    csv_re = re.compile(r'''
        (?P<ts>[^,]+),              # timestamp
        (?P<src>[^,]+),(?P<sport>\d+),(?P<dst>[^,]+),(?P<dport>\d+),\d,
        (?P<interval>[^,]+),
        (?P<bytes>\d+),(?P<bits_per_sec>\d+)
        (?:,(?P<jitter>[\d\.]+),(?P<lost>\d+),(?P<total>\d+))?  # UDP-only
        (?:,(?P<retransmits>\d+))?                             # TCP-only
    ''', re.VERBOSE)

    types = ['voip','video','bulk']
    class_rates     = {t: []  for t in types}
    class_data_mbit = {t: 0.0 for t in types}
    host_rates      = defaultdict(list)
    host_data_mbit  = defaultdict(float)

    all_jitters = []
    all_losses  = []

    procs = []
    start = time.time()
    idx = 0

    # 1) launch clients & servers
    while True:
        now = time.time()
        if now - start >= total_time:
            break

        src, dst = random.choice(pairs)
        ftype    = random.choice(types)
        dur      = random.uniform(*dur_range)
        port     = base_port + idx
        t0       = now

        if ftype in ('voip','video'):
            srv_flag = '-u -s -i 1 -y C'
            cli_flag = '-u -b 100k' if ftype=='voip' else '-u -b 5m'
        else:
            srv_flag = '-s -i 1 -y C'
            cli_flag = ''

        net.get(dst).popen(f'iperf {srv_flag} -p {port}')
        cmd = f'iperf {cli_flag} -c {net.get(dst).IP()} -p {port} -t {dur:.2f} -y C'
        print(f"- Burst {idx}: t0={t0-start:6.2f}s  {src}->{dst} [{ftype}] dur={dur:.2f}s")
        proc = net.get(src).popen(cmd)

        procs.append((src, ftype, proc, dur, t0))
        idx += 1
        time.sleep(random.expovariate(1.0/avg_interval))

    cutoff = start + total_time

    # 2) collect & parse
    print("\n--- Burst Results ---")
    print("-"*70)

    for src, ftype, proc, dur, t0 in procs:
        out, _ = proc.communicate()
        lines = out.decode(errors='ignore').splitlines()
        rate = jitter = loss = 0.0

        for line in reversed(lines):
            if line.startswith('2025'):
                m = csv_re.match(line)
                if not m:
                    continue
                rate = float(m.group('bits_per_sec')) / 1e6

                if ftype in ('voip','video'):
                    jitter   = float(m.group('jitter') or 0.0)
                    lost     = int(m.group('lost')   or 0)
                    total_pk = int(m.group('total')  or 0)
                    loss     = 100.0 * lost/total_pk if total_pk>0 else 0.0
                else:
                    retrans  = int(m.group('retransmits') or 0)
                    sent_pk  = int(m.group('bytes')) / 1460.0
                    loss     = 100.0 * retrans/sent_pk if sent_pk>0 else 0.0
                break
        else:
            for line in reversed(lines):
                if 'Mbits/sec' in line:
                    parts = line.split()
                    rate = float(parts[-2])
                    break

        # record for overall average
        all_jitters.append(jitter)
        all_losses .append(loss)

        t_end_actual = min(cutoff, t0 + dur)
        actual_dur   = max(0.0, t_end_actual - t0)
        rel_t0       = t0 - start

        print(f"t0={rel_t0:6.2f}s ; TYPE={ftype:<5} ; "
              f"rate= {rate:8.3f}Mbps ; jitter={jitter:6.2f}ms ; "
              f"loss={loss:6.2f}% ; dur={dur:5.2f}s ; actual={actual_dur:5.2f}s")

        class_rates[ftype].append(rate)
        host_rates[src].append(rate)
        class_data_mbit[ftype] += rate * actual_dur
        host_data_mbit[src]    += rate * actual_dur

    # 3) summary
    print("\n=== SUMMARY ===")
    total_data_mbit = sum(class_data_mbit.values())
    avg_tp = total_data_mbit / total_time
    print(f"Overall avg throughput = {avg_tp:.2f} Mbit/s")
    print(f"Total data = {total_data_mbit:.2f} Mbit (~{total_data_mbit/8:.2f} MByte)\n")

    # print overall average jitter & loss
    if all_jitters:
        print(f"Average jitter across all bursts = {sum(all_jitters)/len(all_jitters):.2f} ms")
    if all_losses:
        print(f"Average packet loss across all bursts = {sum(all_losses)/len(all_losses):.2f} %\n")

    all_rates = [r for rates in host_rates.values() for r in rates]
    if all_rates:
        print(f"Overall fairness_index = {jain(all_rates):.3f}")
    for t in types:
        if class_rates[t]:
            print(f"{t.capitalize():<5} fairness_index = {jain(class_rates[t]):.5f}")
    print()

    # 4) per-host
    print("=== HOST-LEVEL THROUGHPUT & FAIRNESS ===")
    for h in sorted(host_data_mbit.keys(), key=lambda x: int(x.lstrip('h'))):
        th = host_data_mbit[h] / total_time
        fi = jain(host_rates[h])
        print(f"{h:4} throughput = {th:5.2f} Mbit/s, host fairness_index = {fi:.5f}")
