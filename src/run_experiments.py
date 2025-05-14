#!/usr/bin/env python3

import os
import sys
import time

# Ensure `src/` is on the import path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from mininet.net import Mininet
from mininet.node import Controller,RemoteController, OVSSwitch
from mininet.link import TCLink

from topologies import ExtendedStarTopo, ThreeTierTopo
from traffic_tests.run_ping import run_ping
from traffic_tests.run_stress_test_iperf_tcp import run_stress_test_iperf_tcp
from traffic_tests.run_traffic_mix_voip_video_bulk import run_traffic_mix_voip_video_bulk
from traffic_tests.run_traffic_mix_voip_video_bulk_bursty import run_traffic_mix_voip_video_bulk_bursty

# Experiment parameters
NUM_HOSTS   = 16
HOSTS_PER_SWITCH = NUM_HOSTS // 2
BW          = 100    # Mbps for host–edge & edge–agg links
CORE_BW     = 100    # Mbps for core–agg links
DELAY       = '1ms'
DURATION    = 60     # seconds for each iperf test

def run_on_topology(name, topo):
    """
    Bring up Mininet with the given topology, run all tests, then tear down.
    """
    print(f"\n=== EXPERIMENTS ON {name} ===\n")
    print(f"Experiment parameters:\n"
          f"  - Number of hosts: {NUM_HOSTS}\n"
          f"  - Host bandwidth: {BW} Mbps\n"
          f"  - Core bandwidth: {CORE_BW} Mbps\n"
          f"  - Delay: {DELAY}\n"
          f"  - Duration: {DURATION} seconds\n")

    net = Mininet(
    topo=topo,
    controller=lambda name: RemoteController(
        name,
        ip='192.168.184.129',    
        port=6633         
    ),
    switch=OVSSwitch,
    link=TCLink
)
    net.start()

    # Define pairs: first half hosts -> second half
    half = NUM_HOSTS // 2
    pairs = [(f'h{i}', f'h{i+half}') for i in range(1, half+1)]

    # 1) Connectivity
    run_ping(net)

    # 2) TCP stress test
    run_stress_test_iperf_tcp(
        net,
        pairs,
        duration=DURATION,
        base_port=5000
    )

    # 3) Triple-mix VoIP/Video/Bulk for first half hosts
    #    (h1-h8) -> (h9-h16)
    run_traffic_mix_voip_video_bulk(
        net,
        pairs,
        duration=DURATION,
        base_port=6000
    )

    # 4) Bursty random traffic, VoIP/Video/Bulk
    run_traffic_mix_voip_video_bulk_bursty(
        net,
        pairs,
        total_time=DURATION,
        avg_interval=0.5,
        dur_range=(1, 60),
        base_port=7000
    )

    net.stop()


if __name__ == '__main__':
    # 1) Extended Star topology
    extended_star_topo = ExtendedStarTopo(
        hosts_per_switch=HOSTS_PER_SWITCH,
        host_bw=BW,
        inter_bw=CORE_BW,
        delay=DELAY
    )
    # Run each experiment independently to avoid issues with Ryu controller
    
    run_on_topology('ExtendedStarTopo', extended_star_topo)

    # 2) Three-tier topology
    three_topo = ThreeTierTopo(
        num_hosts=NUM_HOSTS,
        bw=BW,
        core_bw=CORE_BW,
        delay=DELAY
    )
    #run_on_topology('ThreeTierTopo', three_topo)
