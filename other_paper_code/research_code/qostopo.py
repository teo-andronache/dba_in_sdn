from mininet.node import RemoteController, CPULimitedHost
from mininet.net import Mininet
from mininet.topo import Topo
from mininet.link import TCLink
from mininet.log import setLogLevel
from mininet.cli import CLI
import time
import os
import requests as rest
import json
import math
import random

class QosTopo(Topo):
    def build(self):
        DELAY = "1ms"
        BW = 100        # link bandwidth in Mbps
        CPU_F = 4 / 8   # number of cores / number of hosts

        # add hosts - left side
        h1 = self.addHost("h1", ip="192.168.0.121/24",
                          mac="00:00:00:00:00:21", cpu=CPU_F)
        h2 = self.addHost("h2", ip="192.168.0.122/24",
                          mac="00:00:00:00:00:22", cpu=CPU_F)
        h3 = self.addHost("h3", ip="192.168.0.123/24",
                          mac="00:00:00:00:00:23", cpu=CPU_F)
        h4 = self.addHost("h4", ip="192.168.0.124/24",
                          mac="00:00:00:00:00:24", cpu=CPU_F)

        # add hosts - right side
        h5 = self.addHost("h5", ip="192.168.0.131/24",
                          mac="00:00:00:00:00:31", cpu=CPU_F)
        h6 = self.addHost("h6", ip="192.168.0.132/24",
                          mac="00:00:00:00:00:32", cpu=CPU_F)
        h7 = self.addHost("h7", ip="192.168.0.133/24",
                          mac="00:00:00:00:00:33", cpu=CPU_F)
        h8 = self.addHost("h8", ip="192.168.0.134/24",
                          mac="00:00:00:00:00:34", cpu=CPU_F)

        # add switches
        s1 = self.addSwitch("s1", protocols="OpenFlow13")
        s2 = self.addSwitch("s2", protocols="OpenFlow13")
        s3 = self.addSwitch("s3", protocols="OpenFlow13")
        s4 = self.addSwitch("s4", protocols="OpenFlow13")

        # connect left hosts to s1
        self.addLink(h1, s1)
        self.addLink(h2, s1)
        self.addLink(h3, s1)
        self.addLink(h4, s1)

        # connect right hosts to s4
        self.addLink(h5, s4)
        self.addLink(h6, s4)
        self.addLink(h7, s4)
        self.addLink(h8, s4)

        # connect switches in a line s1–s2–s3–s4
        self.addLink(s1, s2, cls=TCLink, bw=BW, delay=DELAY)
        self.addLink(s2, s3, cls=TCLink, bw=BW, delay=DELAY)
        self.addLink(s3, s4, cls=TCLink, bw=BW, delay=DELAY)
# end class

topos = {"qos": (lambda: QosTopo())}


def main():
    setLogLevel("info")
    topo = QosTopo()
    controller = RemoteController("ryu_cont", ip="127.0.0.1", port=6633)
    net = Mininet(topo=topo, controller=controller,
                  link=TCLink, host=CPULimitedHost)
    net.start()
    time.sleep(0.5)

    # Quick connectivity check
    print("----------------------------------------")
    t0 = time.time()
    net.pingAll()
    t1 = time.time()
    print("Ping-all took %.3f sec\n" % (t1 - t0))

    # -------------------
    # QoS meters and flows
    # -------------------
    # Base “nominal” rates (kbps) for each of four flows
    bw = [35000, 25000, 15000, 5000]  # sum = 80 000 kbps

    # Install static meters on dpid=2 and dpid=3
    # (these are “initial” limits; your controller might overwrite later)
    for dpid in (2, 3):
        addMeter(dpid=dpid, meter_id=1, rate=43500)
        addMeter(dpid=dpid, meter_id=2, rate=26100)
        addMeter(dpid=dpid, meter_id=3, rate=17400)
        addMeter(dpid=dpid, meter_id=4, rate=13000)

    # Create one flow/meter pair per client (UDP dst ports 5111–5114)
    # on both switches (dpid=2,3)
    for dpid in (2, 3):
        addFlow(dpid=dpid, udp_dst=5111, meter_id=1)
        addFlow(dpid=dpid, udp_dst=5112, meter_id=2)
        addFlow(dpid=dpid, udp_dst=5113, meter_id=3)
        addFlow(dpid=dpid, udp_dst=5114, meter_id=4)

    # Grab host objects
    h1, h2, h3, h4, h5, h6, h7, h8 = net.get(
        "h1", "h2", "h3", "h4", "h5", "h6", "h7", "h8"
    )

    # Clean and create log directory
    folder = "Logs"
    os.system("sudo rm -f Results/" + folder + "/*")
    os.system("mkdir -p Results/" + folder)
    time.sleep(0.5)

    # Launch iperf UDP servers on h5–h8 (one per port 5111..5114)
    ti = "2"   # server‐side reporting interval
    h5.cmd(f"iperf -s -u -p 5111 -i {ti} >> Results/{folder}/server_h5.txt &")
    h6.cmd(f"iperf -s -u -p 5112 -i {ti} >> Results/{folder}/server_h6.txt &")
    h7.cmd(f"iperf -s -u -p 5113 -i {ti} >> Results/{folder}/server_h7.txt &")
    h8.cmd(f"iperf -s -u -p 5114 -i {ti} >> Results/{folder}/server_h8.txt &")

    # ------------------------------------
    # Main loop: every 10s, compute new rate
    # ------------------------------------
    duration = 60                     # total experiment length (seconds)
    start_time = time.time()
    elapsed = 0.0

    # Give each flow its own phase shift so they do NOT move in lock‐step
    phases = [0.0, math.pi/2, math.pi, 3*math.pi/2]

    print("Starting 10s interval iperf bursts\n")

    while elapsed < duration:
        # How long each iperf client should run this round
        burst_duration = "10"      # -t 10 seconds
        interval = 10  # interval for iperf clients to run before changing rates; interval to sleep 

        t = time.time() - start_time

        # Compute a smooth ±20% sine‐wave demand with different phase for each flow
        d0 = dynamic_demand(bw[0], t, phases[0])
        d1 = dynamic_demand(bw[1], t, phases[1])
        d2 = dynamic_demand(bw[2], t, phases[2])
        d3 = dynamic_demand(bw[3], t, phases[3])

        # Add a small ±20% random jitter on top of the sine‐wave value
        y0 = random.randint(int(d0 - 0.2*d0), int(d0 + 0.2*d0))
        y1 = random.randint(int(d1 - 0.2*d1), int(d1 + 0.2*d1))
        y2 = random.randint(int(d2 - 0.2*d2), int(d2 + 0.2*d2))
        y3 = random.randint(int(d3 - 0.2*d3), int(d3 + 0.2*d3))

        # Format for iperf UDP bandwidth argument
        b0 = f"{(y0/1000):.3f}m"
        b1 = f"{(y1/1000):.3f}m"
        b2 = f"{(y2/1000):.3f}m"
        b3 = f"{(y3/1000):.3f}m"

        # Launch four iperf clients (one per left‐side host), each for 10s
        h1.cmd(f"iperf -u -c {h5.IP()} -p 5111 -b {b0} -i {interval} -t {burst_duration} >> Results/{folder}/client_h1.txt &")
        h2.cmd(f"iperf -u -c {h6.IP()} -p 5112 -b {b1} -i {interval} -t {burst_duration} >> Results/{folder}/client_h2.txt &")
        h3.cmd(f"iperf -u -c {h7.IP()} -p 5113 -b {b2} -i {interval} -t {burst_duration} >> Results/{folder}/client_h3.txt &")
        h4.cmd(f"iperf -u -c {h8.IP()} -p 5114 -b {b3} -i {interval} -t {burst_duration} >> Results/{folder}/client_h4.txt &")

        # Sleep exactly 10s; by the time we wake up, each iperf client has completed its 10s run
        time.sleep(interval)
        elapsed = time.time() - start_time

        deleteFlow(dpid=2, udp_dst=5111, meter_id=1)
        deleteFlow(dpid=3, udp_dst=5111, meter_id=1)
        deleteFlow(dpid=2, udp_dst=5112, meter_id=2)
        deleteFlow(dpid=3, udp_dst=5112, meter_id=2)
        deleteFlow(dpid=2, udp_dst=5113, meter_id=3)
        deleteFlow(dpid=3, udp_dst=5113, meter_id=3)
        deleteFlow(dpid=2, udp_dst=5114, meter_id=4)
        deleteFlow(dpid=3, udp_dst=5114, meter_id=4)

        addFlow(dpid=2, udp_dst=5111, meter_id=1)
        addFlow(dpid=3, udp_dst=5111, meter_id=1)
        addFlow(dpid=2, udp_dst=5112, meter_id=2)
        addFlow(dpid=3, udp_dst=5112, meter_id=2)
        addFlow(dpid=2, udp_dst=5113, meter_id=3)
        addFlow(dpid=3, udp_dst=5113, meter_id=3)
        addFlow(dpid=2, udp_dst=5114, meter_id=4)
        addFlow(dpid=3, udp_dst=5114, meter_id=4)

        # Give the controller ~10 s to modify any meters if needed
        time.sleep(10)

    # Finished
    net.stop()
# end main


def dynamic_demand(base, t, phase=0.0):
    """
    Return a time-varying demand (in kbps) that oscillates around `base` by ±20%.
    Each call also applies a phase shift so the four hosts are out of sync.

      base:  nominal rate in kbps
      t:     elapsed time in seconds
      phase: phase offset (radians)

    Formula: base * [1 + 0.2·sin(2π·(t/T) + phase)], where T=60 s.
    """
    T = 60.0
    amplitude = 0.2
    ωt = 2 * math.pi * ((t % T) / T)
    return base * (1 + amplitude * math.sin(ωt + phase))


def addMeter(dpid, meter_id, rate):
    payload = {
        "dpid": dpid,
        "flags": "KBPS",
        "meter_id": meter_id,
        "bands": [
            {"type": "DROP", "rate": rate, "burst_size": 0}
        ]
    }
    rest.post("http://127.0.0.1:8080/stats/meterentry/add",
              data=json.dumps(payload, indent=4),
              headers={"Content-Type": "application/json"})


def addFlow(dpid, udp_dst, meter_id):
    manageFlow(dpid, udp_dst, meter_id,
               "http://127.0.0.1:8080/stats/flowentry/add")


def deleteFlow(dpid, udp_dst, meter_id):
    manageFlow(dpid, udp_dst, meter_id,
               "http://127.0.0.1:8080/stats/flowentry/delete")


def manageFlow(dpid, udp_dst, meter_id, url):
    payload = {
        "dpid": dpid,
        "cookie": 1,
        "cookie_mask": 1,
        "table_id": 0,
        "idle_timeout": 0,
        "hard_timeout": 0,
        "priority": 2,
        "flags": 1,
        "match": {
            "udp_dst": udp_dst,
            "ip_proto": 17,
            "eth_type": 2048
        },
        "actions": [
            {"type": "METER", "meter_id": meter_id},
            {"type": "OUTPUT", "port": 2}
        ]
    }
    rest.post(url, data=json.dumps(payload, indent=4),
              headers={"Content-Type": "application/json"})


if __name__ == "__main__":
    main()