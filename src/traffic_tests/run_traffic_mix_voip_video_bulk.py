#!/usr/bin/env python

import re
import time

def run_traffic_mix_voip_video_bulk(net, pairs,
                         duration=10,
                         base_port=6000):
    """
    For each (src, dst) in `pairs`, launch three concurrent flows:
      - VoIP   (UDP @ 100k)
      - Video  (UDP @ 5m)
      - Bulk   (TCP)
    Then parse each flow's rate and print per-flow stats plus:
      - overall average & total throughput
      - Jain fairness per class
      - Jain fairness per host

    Args:
      net        : Mininet instance
      pairs      : list of (srcHostName, dstHostName) tuples
      duration   : test duration for each flow (sec)
      base_port  : starting UDP/TCP port; each flow uses base_port + idx
    """
    types = ['voip', 'video', 'bulk']
    # build flat list of flows
    flows = [(src, dst, ftype) for src, dst in pairs for ftype in types]

    print('*** TEST: Triple-mix VoIP/Video/Bulk ***')
    # 1) start servers
    servers = []
    for idx, (_, dst, ftype) in enumerate(flows, start=1):
        port = base_port + idx
        srv = net.get(dst)
        flag = '-u -s' if ftype in ('voip', 'video') else '-s'
        # print(f'  [S] {dst} {ftype} server @ port {port}')
        servers.append(srv.popen(f'iperf {flag} -p {port}'))

    time.sleep(1)

    # regex to match Kbits/sec or Mbits/sec
    pat = re.compile(r'([\d\.]+)\s+([KM]bits/sec)')
    # prepare data containers
    class_rates = {t: [] for t in types}
    host_totals = {src: 0.0 for src, _ in pairs}

    # 2) start clients
    clients = []
    for idx, (src, dst, ftype) in enumerate(flows, start=1):
        port = base_port + idx
        cli = net.get(src)
        dst_h = net.get(dst)
        if ftype == 'voip':
            args = '-u -b 100k'
        elif ftype == 'video':
            args = '-u -b 5m'
        else:
            args = ''
        # print(f'  [C] {src}->{dst} {ftype} @ port {port}')
        clients.append((src, ftype, cli.popen(
            f'iperf {args} -c {dst_h.IP()} -p {port} -t {duration}'
        )))

    # 3) collect results
    for src, ftype, p in clients:
        out, _ = p.communicate()
        text = out.decode(errors='ignore')
        m = pat.search(text)
        rate = 0.0
        if m:
            val = float(m.group(1))
            unit = m.group(2)
            rate = val/1000.0 if unit.startswith('K') else val
        print(f'{src} [{ftype}] = {rate:.2f} Mbit/s')
        class_rates[ftype].append(rate)
        host_totals[src] += rate

    # tear down servers
    for p in servers:
        p.terminate()

    # 4) summary statistics
    print('\n=== SUMMARY ===')
    # overall
    all_rates = [r for rates in class_rates.values() for r in rates]
    if all_rates:
        total = sum(all_rates)
        avg = total/len(all_rates)
        j_all = (total**2)/(len(all_rates)*sum(r*r for r in all_rates))
        print(f'Overall average_throughput = {avg:.2f} Mbit/s')
        print(f'Overall total_throughput   = {total:.2f} Mbit/s')
        print(f'Overall fairness_index     = {j_all:.3f}')
    else:
        print('No flows completed')

    # per-class
    for ftype in types:
        rates = class_rates[ftype]
        if rates:
            total_c = sum(rates)
            j_c = (total_c**2)/(len(rates)*sum(r*r for r in rates))
            print(f'{ftype.capitalize()} fairness_index = {j_c:.3f}')
        else:
            print(f'No {ftype} flows')

    # per-host
    host_rates = list(host_totals.values())
    if host_rates:
        total_h = sum(host_rates)
        avg_h = total_h/len(host_rates)
        j_h = (total_h**2)/(len(host_rates)*sum(r*r for r in host_rates))
        print(f'Host-level avg_throughput = {avg_h:.2f} Mbit/s')
        print(f'Host-level fairness_index = {j_h:.3f}')
    else:
        print('No hosts data')
