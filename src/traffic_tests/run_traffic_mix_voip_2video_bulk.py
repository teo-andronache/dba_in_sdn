#!/usr/bin/env python3
"""
traffic_tests/run_traffic_mix_voip_2video_bulk.py

1 × VoIP  (100 kbit/s UDP)
2 × Video (5    Mbit/s UDP each)
1 × Bulk  (TCP)                … per (src,dst) pair
"""

import re
import time


def run_traffic_mix_voip_2video_bulk(net, pairs, duration=10):
    types_stats = ['voip', 'video', 'bulk']

    # ---------------------------------------------------------------------
    # 1) Build list of individual flows (we have two *video* flows / pair)
    # ---------------------------------------------------------------------
    flows = []
    for src, dst in pairs:
        flows.append((src, dst, 'voip'))
        flows.append((src, dst, 'video'))
        flows.append((src, dst, 'video'))
        flows.append((src, dst, 'bulk'))

    print('*** TEST: 1 VoIP + 2 Video + 1 Bulk per source ***')

    # ---------------------------------------------------------------------
    # 2) Simple port generators per class
    # ---------------------------------------------------------------------
    ports = dict(voip=5000, video=6000, bulk=7000)

    def next_port(ftype):
        port = ports[ftype]
        ports[ftype] = 5000 if ftype == 'voip'  and port >= 5999 else \
                       6000 if ftype == 'video' and port >= 6999 else \
                       7000 if ftype == 'bulk'  and port >= 7999 else \
                       port + 1
        return port

    # ---------------------------------------------------------------------
    # 3) Regex + data containers
    # ---------------------------------------------------------------------
    pat = re.compile(r'([\d\.]+)\s+([KM]bits/sec)')
    class_rates = {t: [] for t in types_stats}
    host_totals = {src: 0.0 for src, _ in pairs}

    # ---------------------------------------------------------------------
    # 4) Start iperf servers  (plain-text, no “-y C”)
    # ---------------------------------------------------------------------
    servers = []
    for _, dst, ftype in flows:
        port = next_port(ftype)
        flag = '-u -s' if ftype in ('voip', 'video') else '-s'
        servers.append(net.get(dst).popen(f'iperf {flag} -p {port}'))

    time.sleep(1)

    # ---------------------------------------------------------------------
    # 5) Start iperf clients  (reset ports first)
    # ---------------------------------------------------------------------
    ports.update(voip=5000, video=6000, bulk=7000)
    clients = []
    for src, dst, ftype in flows:
        port = next_port(ftype)
        if   ftype == 'voip':  args = '-u -b 100k'
        elif ftype == 'video': args = '-u -b 5m'
        else:                  args = ''
        cmd = f'iperf {args} -c {net.get(dst).IP()} -p {port} -t {duration}'
        clients.append((src, dst, ftype, net.get(src).popen(cmd)))

    # ---------------------------------------------------------------------
    # 6) Collect results
    # ---------------------------------------------------------------------
    for src, dst, ftype, proc in clients:
        out, _ = proc.communicate()
        txt = out.decode(errors='ignore')
        m   = pat.search(txt)
        rate = float(m.group(1))/1000 if m and m.group(2).startswith('K') \
               else float(m.group(1)) if m else 0.0
        print(f'{src}->{dst} [{ftype}] = {rate:.3f} Mbit/s')
        class_rates[ftype].append(rate)
        host_totals[src] += rate

    # stop servers
    for p in servers:
        p.terminate()

    # ---------------------------------------------------------------------
    # 7) Summaries
    # ---------------------------------------------------------------------
    print('=== SUMMARY ===')
    all_rates = [r for sub in class_rates.values() for r in sub]
    total     = sum(all_rates)
    if total:
        j_overall = (total**2) / (len(all_rates) * sum(r*r for r in all_rates))
        print(f'Overall total_throughput   = {total:.2f} Mbit/s')
        print(f'Overall fairness_index     = {j_overall:.3f}')
    else:
        print('No flows completed')
        return

    # per-class
    for ftype in types_stats:
        rates = class_rates[ftype]
        if not rates:
            print(f'No {ftype} flows')
            continue
        tot_c = sum(rates)
        den   = len(rates) * sum(r*r for r in rates)
        jain  = (tot_c**2) / den if den else 0.0
        pct   = 100 * tot_c / total
        print(f'{ftype.capitalize():5s}: throughput={tot_c:7.2f} Mb/s '
              f'({pct:5.1f} %)   fairness={jain:.3f}')

    # per-host
    host_rates = list(host_totals.values())
    tot_h = sum(host_rates)
    den_h = len(host_rates) * sum(r*r for r in host_rates)
    j_h   = (tot_h**2) / den_h if den_h else 0.0
    avg_h = tot_h / len(host_rates)
    print(f'Host-level avg_throughput = {avg_h:.2f} Mbit/s')
    print(f'Host-level fairness_index = {j_h:.3f}')

    print("~~~ 1 VoIP + 2 Video + 1 Bulk test completed. ~~~\n")
