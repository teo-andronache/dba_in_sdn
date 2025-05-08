#!/usr/bin/env python

from mininet.topo import Topo
from mininet.net import Mininet
from mininet.node import Controller, RemoteController
from mininet.link import TCLink
from mininet.cli import CLI
from mininet.log import setLogLevel
from traffic_tests.run_ping import run_ping
from traffic_tests.run_stress_test_iperf_tcp import run_stress_test_iperf_tcp
from traffic_tests.run_traffic_mix_voip_video_bulk import run_traffic_mix_voip_video_bulk


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

if __name__ == '__main__':
    TOTAL_HOSTS = 16               # total across both switches
    HOSTS_PER_SWITCH = TOTAL_HOSTS // 2
    HOST_BW = 100                  # Mbps for host links
    INTER_SWITCH_BW = 200          # Mbps for switch-to-switch link
    DELAY = '1ms'
    DURATION = 20                  # seconds for iperf tests

    topo = ExtendedStarTopo(
        hosts_per_switch=HOSTS_PER_SWITCH,
        host_bw=HOST_BW,
        inter_bw=INTER_SWITCH_BW,
        delay=DELAY
    )
    net = Mininet(topo=topo, controller=Controller, link=TCLink)
    net.start()

    # TEST: Basic connectivity
    run_ping(net)

    # TEST: Stress test with TCP iperf 
    # Default pairs: first half hosts -> second half hosts to stress test the bottleneck links
    half = TOTAL_HOSTS // 2
    pairs = [(f'h{i}', f'h{i+half}') for i in range(1, half+1)]
    run_stress_test_iperf_tcp(net, pairs, duration=DURATION, base_port=5000)

    # TEST: Run traffic mix (VoIP, Video, Bulk) between hosts on different switches
    # This will run 24 flows in parallel: 3 flows per host for first 8 hosts
    # (VoIP, Video, Bulk) to the corresponding host on the other switch
    run_traffic_mix_voip_video_bulk(net, pairs, duration=DURATION, base_port=6000)

    # Drop to CLI
    #CLI(net)
    net.stop()
