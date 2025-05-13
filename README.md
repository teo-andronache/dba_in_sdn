# Dynamic Bandwidth Allocation in Software Defined Networks

## Introduction
This repository contains the code for two Mininet topologies (extended-star, three-tier tree) and two Ryu SDN Controller Algorithms (max-min fair share allocation, proactive algorithm). 

## Prerequisites
- Mininet: https://mininet.org/download/ ; install it as a VM, then ssh into it via `ssh mininet@<mininet-vm-ip>` with password `mininet` or set-up ssh keys

## Running the experiments
- Copy the `dba_in_sdn` directory on the Mininet VM
- SSH into mininet
- Run the Ryu SDN Controller 
- Open another terminal in mininet and run the experiments

Commands (fill in the IP address of the mininet-vm):
```bash
teo@ubuntu:~$ scp -r dba_in_sdn mininet@<mininet-vm-ip>:~/

teo@ubuntu:~$ ssh mininet@<mininet-vm-ip>

mininet@mininet-vm:~$ cd dba_in_sdn/src/controllers/

mininet@mininet-vm:~/dba_in_sdn/src/controllers$ ryu-manager simple_switch_13.py

# In another terminal, start the experiments
teo@ubuntu:~$ ssh mininet@<mininet-vm-ip>

mininet@mininet-vm:~$ cd dba_in_sdn/src

mininet@mininet-vm:~/dba_in_sdn/src$ sudo python3 run_experiments.py
```

## Topologies
### Extended star topology
Characteristics: 
- 2 switches
- 16 hosts (8 per switch)
- 200 Mbps link between switches
- 100 Mbps links between hosts and their switch

![Alt text for screen‐readers](images/ExtendedStarTopo.svg)

### Three tier tree topology
Characteristics: 
- 7 switches: 1 core, 2 aggregation, 4 edge
- 16 hosts (4 per edge switch)
- 200 Mbps links between the core and aggregation switches
- 100 Mbps links between the aggregation switches and edge switches, and between the edge switches and hosts
![Alt text for screen‐readers](images/ThreeTierTopo.svg)

