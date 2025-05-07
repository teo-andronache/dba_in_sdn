#!/usr/bin/env python

from mininet.topo import Topo
from mininet.net import Mininet
from mininet.node import RemoteController, Controller
from mininet.link import TCLink
from mininet.cli import CLI
from mininet.log import setLogLevel
import time

class ThreeTierTopo(Topo):
    """
    Three-tier topology with configurable parameters:
      - 1 core switch
      - 2 aggregation switches
      - 4 edge switches
      - total hosts connected equally across edge switches
      All links have configurable bandwidth and delay.
    """
    def __init__(self, num_hosts=16, bw=100, delay='10ms', **opts):
        self.num_hosts = num_hosts
        self.bw = bw
        self.delay = delay
        super().__init__(**opts)

    def build(self):
        core = self.addSwitch('s1')
        aggr_switches = []
        for i in range(2):
            sw = self.addSwitch(f's{2 + i}')
            aggr_switches.append(sw)
            self.addLink(core, sw, bw=self.bw, delay=self.delay)

        hosts_per_edge = self.num_hosts // 4
        host_id = 1
        for i in range(4):
            edge_sw = self.addSwitch(f's{4 + i}')
            parent_aggr = aggr_switches[i // 2]
            self.addLink(parent_aggr, edge_sw, bw=self.bw, delay=self.delay)
            for _ in range(hosts_per_edge):
                h = self.addHost(f'h{host_id}')
                self.addLink(edge_sw, h, bw=self.bw, delay=self.delay)
                host_id += 1


def run_ping(net):
    print('*** TEST: Ping all hosts')
    net.pingAll()


def run_iperf_scenario(net, pairs, duration=10, base_port=5000):
    servers = []
    for idx, (src, dst) in enumerate(pairs, start=1):
        port = base_port + idx
        srv = net.get(dst)
        print(f'*** Starting iperf server on {srv.name} port {port}')
        servers.append(srv.popen(f'iperf -s -p {port}'))
    time.sleep(1)

    clients = []
    for idx, (src, dst) in enumerate(pairs, start=1):
        cli = net.get(src)
        dst_h = net.get(dst)
        port = base_port + idx
        print(f'*** Testing {cli.name} -> {dst_h.name} on port {port}')
        clients.append((cli, cli.popen(f'iperf -c {dst_h.IP()} -p {port} -t {duration}')))

    for cli, p in clients:
        out, _ = p.communicate()
        print(f'*** {cli.name} result:\n{out.decode().strip()}')

    for p in servers:
        p.terminate()


def run_parallel_tcp_scenario(net, pairs, num_streams=3, duration=10, base_port=10000):
    """
    Run num_streams parallel TCP flows for each (src, dst) pair concurrently.
    """
    servers = []
    # Start all servers
    for idx, (src, dst) in enumerate(pairs):
        for s in range(num_streams):
            port = base_port + idx * num_streams + s
            srv = net.get(dst)
            print(f'*** Starting parallel TCP server on {srv.name} port {port}')
            servers.append(srv.popen(f'iperf -s -p {port}'))

    time.sleep(1)
    # Start all clients
    clients = []
    for idx, (src, dst) in enumerate(pairs):
        for s in range(num_streams):
            port = base_port + idx * num_streams + s
            cli = net.get(src)
            dst_h = net.get(dst)
            print(f'*** {cli.name} -> {dst_h.name} parallel stream {s+1} on port {port}')
            clients.append(((src, dst, s), cli.popen(
                f'iperf -c {dst_h.IP()} -p {port} -t {duration}')))  

    # Collect results
    for (src, dst, s), p in clients:
        out, _ = p.communicate()
        print(f'*** {src}->{dst} stream {s+1} result:\n{out.decode().strip()}')

    # Stop servers
    for p in servers:
        p.terminate()


if __name__ == '__main__':
    setLogLevel('info')
    NUM_HOSTS = 16
    BW = 100
    DELAY = '1ms'
    DURATION = 60
    topo = ThreeTierTopo(num_hosts=NUM_HOSTS, bw=BW, delay=DELAY)
    net = Mininet(
        topo=topo,
        controller=Controller,
        #controller=lambda name: RemoteController(name, ip='192.168.184.129', port=6653),
        link=TCLink
    )
    net.start()

    run_ping(net)
    half = NUM_HOSTS // 2
    pairs = [(f'h{i}', f'h{i+half}') for i in range(1, half+1)]
    run_iperf_scenario(net, pairs, duration=DURATION, base_port=5000)

    print('*** TEST: 3 parallel TCP streams per pair, all at once')
    run_parallel_tcp_scenario(net, pairs,
                              num_streams=3,
                              duration=DURATION,
                              base_port=10000)

    CLI(net)
    net.stop()
