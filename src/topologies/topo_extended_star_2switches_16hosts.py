#!/usr/bin/env python

from mininet.topo import Topo

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