import re,time

def run_stress_test_iperf_tcp(net, pairs, duration=10, base_port=5000):
    """Run iperf TCP for each pair; log per-flow throughput and Jain fairness."""
    print('*** TEST: Stress test iperf TCP ***')
    servers = []
    for idx, (src, dst) in enumerate(pairs, start=1):
        port = base_port + idx
        srv = net.get(dst)
        servers.append(srv.popen(f'iperf -s -p {port}'))
    time.sleep(1)
    throughputs = []
    pat = re.compile(r'([\d\.]+) Mbits/sec')
    clients = []
    for idx, (src, dst) in enumerate(pairs, start=1):
        cli = net.get(src)
        dst_h = net.get(dst)
        port = base_port + idx
        clients.append((src, dst, cli.popen(f'iperf -c {dst_h.IP()} -p {port} -t {duration}')))
    for src, dst, p in clients:
        out, _ = p.communicate()
        text = out.decode(errors='ignore')
        m = pat.search(text)
        if m:
            val = float(m.group(1))
            throughputs.append(val)
            print(f'{src}->{dst} throughput={val:.2f} Mbit/s')
    for p in servers: p.terminate()
    if throughputs:
        n = len(throughputs)
        fairness_index = (sum(throughputs)**2) / (n * sum(x*x for x in throughputs))
        print(f'avg_throughput={sum(throughputs)/n:.2f} Mbit/s')
        print(f'total_throughput={sum(throughputs):.2f} Mbit/s')
        print(f'fairness_index={fairness_index:.3f}')
    else:
        print('throughput: no data')