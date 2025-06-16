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
    initial_meter_rates = [50000, 30000, 15000, 5000]

    # Test cases keeping the initial meter ratios

    # CASE 1: Same ratios as meter rates, sum up to 80 000 kbps
    bw = [40000, 24000, 12000, 4000]

    # CASE 2: Same ratios, sum up to 90 000 kbps
    #bw = [45000, 27000, 13500, 4500]  # sum = 90 000 kbps

    # CASE 3: Same ratios, sum up to 100 000 kbps
    #bw = [50000, 30000, 15000, 5000]  # sum = 100 000 kbps

    # CASE 4: Same ratios, sum up to 110 000 kbps
    #bw = [55000, 33000, 16500, 5500]  # sum = 110 000 kbps

    # CASE 5: Same ratios, sum up to 120 000 kbps
    bw = [60000, 36000, 18000, 6000]  # sum = 120 000 kbps

    #########################################################

    # CASE 6:  all classes are well under the nominal rate, 50% under the initial meter allocations
    #bw = [25000, 15000, 7500, 2500]  # sum = 50 000 kbps

    # CASE 7: class 1 is overperforming by 20% over the initial meter, class 2, 3, 4 are underperforming by 50% under the initial meter
    #bw = [60000, 15000, 7500, 2500]  # sum = 90 000 kbps

    # CASE 8: class 1 is underperforming by 50% under the initial meter, class 2, 3, 4 are overperforming by 20% over the initial meter
    #bw = [25000, 36000, 18000, 6000]  # sum = 85 000 kbps

    # CASE 9: classes 1,2,3 are underperforming by 20% under the initial meter, class 4 is overperforming by 100% over the initial meter
    #bw = [40000, 24000, 12000, 10000]  # sum = 86 000 kkps

    # Install initial static meters on dpid=2 and dpid=3
    for dpid in (2,3):
        addMeter(dpid=dpid, meter_id=1, rate=initial_meter_rates[0])  
        addMeter(dpid=dpid, meter_id=2, rate=initial_meter_rates[1])  
        addMeter(dpid=dpid, meter_id=3, rate=initial_meter_rates[2])  
        addMeter(dpid=dpid, meter_id=4, rate=initial_meter_rates[3])  

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
    ti = "1"   # server‐side reporting interval
    h5.cmd(f"iperf -s -u -p 5111 -i {ti} -y C >> Results/{folder}/server_h5.csv &")
    h6.cmd(f"iperf -s -u -p 5112 -i {ti} -y C >> Results/{folder}/server_h6.csv &")
    h7.cmd(f"iperf -s -u -p 5113 -i {ti} -y C >> Results/{folder}/server_h7.csv &")
    h8.cmd(f"iperf -s -u -p 5114 -i {ti} -y C >> Results/{folder}/server_h8.csv &")

    # ------------------------------------
    # Main loop: every interval, compute new rate
    # ------------------------------------
    duration = 300 
    # Interval between bursts, each client runs for 31s then new bandwidth is computed
    # One extra second is needed to allow better server-side reporting.
    interval = 31                    
    start_time = time.time()
    elapsed = 0.0

    # Give each flow its own phase shift so they do NOT move in lock‐step
    phases = [0.0, math.pi/2, math.pi, 3*math.pi/2]

    print(f"Starting {interval} interval iperf bursts\n")

    while elapsed < duration:
        t = time.time() - start_time

        # Compute a smooth ±20% sine‐wave demand with different phase for each flow
        d0 = dynamic_demand(bw[0], t, phases[0])
        d1 = dynamic_demand(bw[1], t, phases[1])
        d2 = dynamic_demand(bw[2], t, phases[2])
        d3 = dynamic_demand(bw[3], t, phases[3])

        # Add a small ±10% random jitter on top of the sine‐wave value
        y0 = random.randint(int(d0 - 0.1*d0), int(d0 + 0.1*d0))
        y1 = random.randint(int(d1 - 0.1*d1), int(d1 + 0.1*d1))
        y2 = random.randint(int(d2 - 0.1*d2), int(d2 + 0.1*d2))
        y3 = random.randint(int(d3 - 0.1*d3), int(d3 + 0.1*d3))

        # Format for iperf UDP bandwidth argument
        b0 = f"{(y0/1000):.3f}m"
        b1 = f"{(y1/1000):.3f}m"
        b2 = f"{(y2/1000):.3f}m"
        b3 = f"{(y3/1000):.3f}m"

        # Launch four iperf clients (one per left‐side host), each for 31s
        h1.cmd(f"iperf -u -c {h5.IP()} -p 5111 -b {b0} -i {interval} -t {interval} -y C >> Results/{folder}/client_h1.csv &")
        h2.cmd(f"iperf -u -c {h6.IP()} -p 5112 -b {b1} -i {interval} -t {interval} -y C >> Results/{folder}/client_h2.csv &")
        h3.cmd(f"iperf -u -c {h7.IP()} -p 5113 -b {b2} -i {interval} -t {interval} -y C >> Results/{folder}/client_h3.csv &")
        h4.cmd(f"iperf -u -c {h8.IP()} -p 5114 -b {b3} -i {interval} -t {interval} -y C >> Results/{folder}/client_h4.csv &")

        # Sleep exactly 31s; by the time we wake up, each iperf client has completed its 31s run
        time.sleep(interval)
        elapsed = time.time() - start_time

        # Give the controller 5s to modify any meters if needed
        time.sleep(1)

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