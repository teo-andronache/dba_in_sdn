#!/usr/bin/env python

import re
import time

def run_traffic_mix_voip_video_bulk(net, pairs,
                         duration=10):
    """
    For each (src, dst) in `pairs`, launch three concurrent flows:
      - VoIP   (UDP @ 100k)
      - Video  (UDP @ 5m)
      - Bulk   (TCP)
    Then parse each flow's rate and print per-flow stats plus:
      - overall average & total throughput
      - Jain fairness per class
      - Jain fairness per host
    """
    types = ['voip', 'video', 'bulk']
    # build flat list of flows
    flows = [(src, dst, ftype) for src, dst in pairs for ftype in types]

    print('*** TEST: Triple-mix VoIP/Video/Bulk ***')
    voip_port  = 5000
    video_port = 6000
    bulk_port  = 7000

    # regex to match Kbits/sec or Mbits/sec
    pat = re.compile(r'([\d\.]+)\s+([KM]bits/sec)')

    # data containers for summary
    class_rates = {t: [] for t in types}
    host_totals = {src: 0.0 for src, _ in pairs}

    # 1) start servers
    servers = []
    for _, dst, ftype in flows:
        if ftype == 'voip':
            port = voip_port
            voip_port += 1
            if voip_port > 5999:
                voip_port = 5000
        elif ftype == 'video':
            port = video_port
            video_port += 1
            if video_port > 6999:
                video_port = 6000
        else:  # bulk
            port = bulk_port
            bulk_port += 1
            if bulk_port > 7999:
                bulk_port = 7000

        srv = net.get(dst)
        flag = '-u -s' if ftype in ('voip', 'video') else '-s'
        servers.append(srv.popen(f'iperf {flag} -p {port}'))

    time.sleep(1)

    # 2) start clients
    clients = []
    # reset port counters
    voip_port  = 5000
    video_port = 6000
    bulk_port  = 7000

    for src, dst, ftype in flows:
        if ftype == 'voip':
            port = voip_port
            voip_port += 1
            if voip_port > 5999:
                voip_port = 5000
        elif ftype == 'video':
            port = video_port
            video_port += 1
            if video_port > 6999:
                video_port = 6000
        else:  # bulk
            port = bulk_port
            bulk_port += 1
            if bulk_port > 7999:
                bulk_port = 7000

        cli = net.get(src)
        dst_h = net.get(dst)
        if ftype == 'voip':
            args = '-u -b 100k'
        elif ftype == 'video':
            args = '-u -b 5m'
        else:
            args = ''
        clients.append((src, dst, ftype, cli.popen(
            f'iperf {args} -c {dst_h.IP()} -p {port} -t {duration}'
        )))

    # 3) collect results
    for src, dst, ftype, p in clients:
        out, _ = p.communicate()
        text = out.decode(errors='ignore')
        m = pat.search(text)
        rate = 0.0
        if m:
            val = float(m.group(1))
            unit = m.group(2)
            rate = val/1000.0 if unit.startswith('K') else val
        print(f'{src}->{dst} [{ftype}] = {rate:.3f} Mbit/s')
        class_rates[ftype].append(rate)
        host_totals[src] += rate

    # tear down servers
    for p in servers:
        p.terminate()

    # 4) summary statistics
    print('=== SUMMARY ===')
    # overall
    all_rates = [r for rates in class_rates.values() for r in rates]
    if all_rates:
        total = sum(all_rates)
        j_all = (total**2)/(len(all_rates)*sum(r*r for r in all_rates))
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

    print("~~~ Triple-mix VoIP/Video/Bulk test completed. ~~~\n")
