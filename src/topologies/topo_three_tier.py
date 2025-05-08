#!/usr/bin/env python

from mininet.topo import Topo

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