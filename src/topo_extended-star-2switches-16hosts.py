#!/usr/bin/env python

from mininet.topo import Topo
from mininet.net import Mininet
from mininet.node import Controller, RemoteController
from mininet.link import TCLink
from mininet.cli import CLI
from mininet.log import setLogLevel
import time

class ExtendedStarTopo(Topo):
    """
    Two-switch extended-star topology with configurable parameters:
      - 2 switches connected by a link
      - each switch has N hosts directly attached
      All host links have configurable bandwidth and delay.
      The inter-switch link has its own bandwidth and same delay.
    """
    def __init__(self, hosts_per_switch=8, host_bw=100, inter_bw=200, delay='10ms', **opts):
        self.hosts_per_switch = hosts_per_switch
        self.host_bw = host_bw
        self.inter_bw = inter_bw
        self.delay = delay
        super().__init__(**opts)

    def build(self):
        # Add two switches
        s1 = self.addSwitch('s1')
        s2 = self.addSwitch('s2')
        # Link between switches
        self.addLink(s1, s2, bw=self.inter_bw, delay=self.delay)

        # Attach hosts to each switch
        host_id = 1
        for sw in (s1, s2):
            for _ in range(self.hosts_per_switch):
                h = self.addHost(f'h{host_id}')
                self.addLink(sw, h, bw=self.host_bw, delay=self.delay)
                host_id += 1


def run_ping(net):
    """Ping all hosts in the network."""
    print('*** TEST: Ping all hosts')
    net.pingAll()


def run_iperf_scenario(net, pairs, duration=10, base_port=5000):
    """
    Run iperf TCP tests for given list of (src, dst) tuples concurrently.
    """
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


if __name__ == '__main__':
    setLogLevel('info')
    # Configurable parameters
    TOTAL_HOSTS = 16               # total across both switches
    HOSTS_PER_SWITCH = TOTAL_HOSTS // 2
    HOST_BW = 100                  # Mbps for host links
    INTER_SWITCH_BW = 200          # Mbps for switch-to-switch link
    DELAY = '1ms'
    DURATION = 60                  # seconds for iperf tests

    topo = ExtendedStarTopo(
        hosts_per_switch=HOSTS_PER_SWITCH,
        host_bw=HOST_BW,
        inter_bw=INTER_SWITCH_BW,
        delay=DELAY
    )
    net = Mininet(
        topo=topo,
        controller=Controller,
        link=TCLink
    )
    net.start()

    # Basic connectivity
    run_ping(net)

    # Default pairs: first half hosts -> second half hosts
    pairs = [(f'h{i}', f'h{i+HOSTS_PER_SWITCH}') for i in range(1, HOSTS_PER_SWITCH+1)]
    run_iperf_scenario(net, pairs, duration=DURATION, base_port=5000)

    # Drop to CLI
    CLI(net)
    net.stop()
