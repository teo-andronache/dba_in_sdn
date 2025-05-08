#!/usr/bin/env python

from mininet.topo import Topo
from mininet.net import Mininet
from mininet.node import RemoteController, Controller
from mininet.link import TCLink
from mininet.cli import CLI
from mininet.log import setLogLevel
from traffic_tests.run_ping import run_ping
from traffic_tests.run_stress_test_iperf_tcp import run_stress_test_iperf_tcp
from traffic_tests.run_traffic_mix_voip_video_bulk import run_traffic_mix_voip_video_bulk


class ThreeTierTopo(Topo):
    """
    Three-tier topology with configurable parameters:
      - 1 core switch
      - 2 aggregation switches
      - 4 edge switches
      - total hosts connected equally across edge switches
      All host-edge and edge-aggregation links have bandwidth `bw`
      Core-aggregation links have bandwidth `core_bw`.
    """
    def __init__(self, num_hosts=16, bw=100, core_bw=200, delay='10ms', **opts):
        self.num_hosts = num_hosts    # total hosts
        self.bw        = bw           # Mbps for host–edge & edge–agg links
        self.core_bw   = core_bw      # Mbps for core–aggregation links
        self.delay     = delay
        super().__init__(**opts)

    def build(self):
        core = self.addSwitch('s1')

        # Aggregation layer: use core_bw here
        aggr_switches = []
        for i in range(2):
            sw = self.addSwitch(f's{2 + i}')
            aggr_switches.append(sw)
            self.addLink(core, sw,
                         bw=self.core_bw,
                         delay=self.delay)

        # Edge layer + hosts: use bw here
        hosts_per_edge = self.num_hosts // 4
        host_id = 1
        for i in range(4):
            edge_sw = self.addSwitch(f's{4 + i}')
            parent_aggr = aggr_switches[i // 2]
            # aggregation-edge
            self.addLink(parent_aggr, edge_sw,
                         bw=self.bw,
                         delay=self.delay)
            # edge-hosts
            for _ in range(hosts_per_edge):
                h = self.addHost(f'h{host_id}')
                self.addLink(edge_sw, h,
                             bw=self.bw,
                             delay=self.delay)
                host_id += 1

if __name__ == '__main__':
    TOTAL_HOSTS = 16
    BW = 100
    CORE_BW = 200
    DELAY = '1ms'
    DURATION = 20
    topo = ThreeTierTopo(num_hosts=TOTAL_HOSTS, bw=BW,core_bw=CORE_BW, delay=DELAY)
    net = Mininet(
        topo=topo,
        controller=Controller,
        #controller=lambda name: RemoteController(name, ip='192.168.184.129', port=6653),
        link=TCLink
    )
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

    #CLI(net)
    net.stop()
