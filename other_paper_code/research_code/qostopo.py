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
		#host and link parameters
		dely = "1ms"	#link delay
		bandwidth = 20	#link bandwidth in MBits
		cpu_f = 4 / 8		#number of cores / number of hosts

		# h1------------|                                      |------------h5
		#               |                                      |
		# h2-------|    |                                      |    |-------h6
		#           --------      --------      --------      --------
		#          / OF S1 /-----/ OF S2 /-----/ OF S3 /-----/ OF S4 /
		#         --------      --------      --------      --------
		# h3-------|    |               \     /               |    |-------h7
		#               |                \   /                |
		# h4------------|              Ryu Controller         |------------h8

		#add hosts - left side
		h1 = self.addHost("h1", ip = "192.168.0.121/24", mac = "00:00:00:00:00:21", cpu = cpu_f)
		h2 = self.addHost("h2", ip = "192.168.0.122/24", mac = "00:00:00:00:00:22", cpu = cpu_f)
		h3 = self.addHost("h3", ip = "192.168.0.123/24", mac = "00:00:00:00:00:23", cpu = cpu_f)
		h4 = self.addHost("h4", ip = "192.168.0.124/24", mac = "00:00:00:00:00:24", cpu = cpu_f)

		#add hosts - right side
		h5 = self.addHost("h5", ip = "192.168.0.131/24", mac = "00:00:00:00:00:31", cpu = cpu_f)
		h6 = self.addHost("h6", ip = "192.168.0.132/24", mac = "00:00:00:00:00:32", cpu = cpu_f)
		h7 = self.addHost("h7", ip = "192.168.0.133/24", mac = "00:00:00:00:00:33", cpu = cpu_f)
		h8 = self.addHost("h8", ip = "192.168.0.134/24", mac = "00:00:00:00:00:34", cpu = cpu_f)

		#add switches
		s1 = self.addSwitch("s1", protocols = "OpenFlow13")
		s2 = self.addSwitch("s2", protocols = "OpenFlow13")
		s3 = self.addSwitch("s3", protocols = "OpenFlow13")
		s4 = self.addSwitch("s4", protocols = "OpenFlow13")

		#add left hosts to switch1
		self.addLink(h1, s1)
		self.addLink(h2, s1)
		self.addLink(h3, s1)
		self.addLink(h4, s1)

		#add right hosts to switch4
		self.addLink(h5, s4)
		self.addLink(h6, s4)
		self.addLink(h7, s4)
		self.addLink(h8, s4)

		#connect switches
		self.addLink(s1, s2, cls = TCLink, bw = bandwidth, delay = dely)
		self.addLink(s2, s3, cls = TCLink, bw = bandwidth, delay = dely)
		self.addLink(s3, s4, cls = TCLink, bw = bandwidth, delay = dely)
	#end def
#end class
topos = {"qos": (lambda: QosTopo())}	#this line is needed if running using sudo mn

def main():
	#setup the network
	setLogLevel("info")
	qostopo = QosTopo()
	ryu_cont = RemoteController("ryu_cont", ip = "127.0.0.1", port = 6633)
	net = Mininet(topo = qostopo, controller = ryu_cont, link = TCLink, host = CPULimitedHost)
	net.start()				#start the network
	time.sleep(0.5)

	#just to make sure theres full connectivity
	print("----------------------------------------")
	t1 = time.time()
	net.pingAll()
	t2 = time.time()
	time.sleep(0.5)
	print("Total time to ping: " + str(t2 - t1))

	#testing parameters
	ti = "2"  # -i reporting interval
	folder = "Logs"
	# bw = [8000, 6000, 4000, 2000]  # total = 20m
	# bw = [7000, 5000, 3000, 1000]  # total = 16m
	# bw = [9000, 7000, 3000, 1000]  # total = 20m
	bw = [9000, 7000, 5000, 3000]  # total = 24m
	# bw = [7000, 5000, 3000, 4000]  # total = 19m

	addMeter(dpid = 2, meter_id = 1, rate = 5000) #initial configured bandwidths
	addMeter(dpid = 2, meter_id = 2, rate = 5000)
	addMeter(dpid = 2, meter_id = 3, rate = 5000)
	addMeter(dpid = 2, meter_id = 4, rate = 5000)

	addMeter(dpid = 3, meter_id = 1, rate = 5000)
	addMeter(dpid = 3, meter_id = 2, rate = 5000)
	addMeter(dpid = 3, meter_id = 3, rate = 5000)
	addMeter(dpid = 3, meter_id = 4, rate = 5000)

	addFlow(dpid = 2, udp_dst = 5111, meter_id = 1)
	addFlow(dpid = 3, udp_dst = 5111, meter_id = 1)
	addFlow(dpid = 2, udp_dst = 5112, meter_id = 2)
	addFlow(dpid = 3, udp_dst = 5112, meter_id = 2)
	addFlow(dpid = 2, udp_dst = 5113, meter_id = 3)
	addFlow(dpid = 3, udp_dst = 5113, meter_id = 3)
	addFlow(dpid = 2, udp_dst = 5114, meter_id = 4)
	addFlow(dpid = 3, udp_dst = 5114, meter_id = 4)

	#get the hosts and create necessary folders for saving the results
	print("Initializing devices...")
	h1, h2, h3, h4, h5, h6, h7, h8 = net.get("h1", "h2", "h3", "h4", "h5", "h6", "h7", "h8")
	os.system("sudo rm -f Results/" + folder + "/*")
	os.system("mkdir -p Results/" + folder)
	time.sleep(0.5)

	#create iperf servers on hosts
	h5.cmd(f"iperf -s -u -p 5111 -i {ti} > Results/{folder}/server_h5.txt &")
	h6.cmd(f"iperf -s -u -p 5112 -i {ti} > Results/{folder}/server_h6.txt &")
	h7.cmd(f"iperf -s -u -p 5113 -i {ti} > Results/{folder}/server_h7.txt &")
	h8.cmd(f"iperf -s -u -p 5114 -i {ti} > Results/{folder}/server_h8.txt &")

	duration = 60  # -t test duration
	t1 = time.time()
	time.sleep(1)
	t2 = time.time()
	offset = t1
	print("Starting tests...")

	while int(t2 - t1) < duration:
		ti = td = "60"
		var = 0.2	#this variance is to generate randomness
		t = int(t2 - offset)

		[x1, y1] = determineBandwidth(bw[0], t + 0)
		y1 = random.randint(int(y1 - var * y1), int(y1 + var * y1))
		b0 = str(float(int(y1) / 1000)) + "m"

		[x1, y1] = determineBandwidth(bw[1], t + 60)
		y1 = random.randint(int(y1 - var * y1), int(y1 + var * y1))
		b1 = str(float(int(y1) / 1000)) + "m"

		[x1, y1] = determineBandwidth(bw[2], t + 120)
		y1 = random.randint(int(y1 - var * y1), int(y1 + var * y1))
		b2 = str(float(int(y1) / 1000)) + "m"

		[x1, y1] = determineBandwidth(bw[3], t + 180)
		y1 = random.randint(int(y1 - var * y1), int(y1 + var * y1))
		b3 = str(float(int(y1) / 1000)) + "m"

		h1.cmd(f"iperf -u -c {h5.IP()} -p 5111 -b {b0} -i {ti} -t {td} > Results/{folder}/client_h1.txt &")
		h2.cmd(f"iperf -u -c {h6.IP()} -p 5112 -b {b1} -i {ti} -t {td} > Results/{folder}/client_h2.txt &")
		h3.cmd(f"iperf -u -c {h7.IP()} -p 5113 -b {b2} -i {ti} -t {td} > Results/{folder}/client_h3.txt &")
		h4.cmd(f"iperf -u -c {h8.IP()} -p 5114 -b {b3} -i {ti} -t {td} > Results/{folder}/client_h4.txt &")

		time.sleep(int(ti))
		t2 = time.time()

		b0 = b1 = b2 = b3 = 0
		h1.cmd(f"iperf -u -c {h5.IP()} -p 5111 -b {b0} -i {ti} -t {td} > Results/{folder}/client_h1.txt &")
		h2.cmd(f"iperf -u -c {h6.IP()} -p 5112 -b {b1} -i {ti} -t {td} > Results/{folder}/client_h2.txt &")
		h3.cmd(f"iperf -u -c {h7.IP()} -p 5113 -b {b2} -i {ti} -t {td} > Results/{folder}/client_h3.txt &")
		h4.cmd(f"iperf -u -c {h8.IP()} -p 5114 -b {b3} -i {ti} -t {td} > Results/{folder}/client_h4.txt &")
		time.sleep(10)

		deleteFlow(dpid = 2, udp_dst = 5111, meter_id = 1)
		deleteFlow(dpid = 3, udp_dst = 5111, meter_id = 1)
		deleteFlow(dpid = 2, udp_dst = 5112, meter_id = 2)
		deleteFlow(dpid = 3, udp_dst = 5112, meter_id = 2)
		deleteFlow(dpid = 2, udp_dst = 5113, meter_id = 3)
		deleteFlow(dpid = 3, udp_dst = 5113, meter_id = 3)
		deleteFlow(dpid = 2, udp_dst = 5114, meter_id = 4)
		deleteFlow(dpid = 3, udp_dst = 5114, meter_id = 4)
		addFlow(dpid = 2, udp_dst = 5111, meter_id = 1)
		addFlow(dpid = 3, udp_dst = 5111, meter_id = 1)
		addFlow(dpid = 2, udp_dst = 5112, meter_id = 2)
		addFlow(dpid = 3, udp_dst = 5112, meter_id = 2)
		addFlow(dpid = 2, udp_dst = 5113, meter_id = 3)
		addFlow(dpid = 3, udp_dst = 5113, meter_id = 3)
		addFlow(dpid = 2, udp_dst = 5114, meter_id = 4)
		addFlow(dpid = 3, udp_dst = 5114, meter_id = 4)
		time.sleep(10)
	#end while

	time.sleep(0.5)
	#CLI(net)	#to bring up the CLI
	net.stop()	#stop the network
#end def

def determineBandwidth(base, t):
	variance = 0.2	#this variance is to map the initial bw to the math functions
	t = t % 300

	y = base
	xout = [0, 60]						#
	yout = [base, base]					#
	if t >= xout[0] and t < xout[1]:
		#print("Linear")
		xin = [0, 1]					#
		yin = [0, 1]					#
		t = mapper(t, xout[0], xout[1], xin[0], xin[1])
		ft = base						#
		x = mapper(t, xin[0], xin[1], xout[0], xout[1])
		y = mapper(ft, yin[0], yin[1], yout[0], yout[1])
		return [x, y]
	#end if

	#y = sin(x)
	xout = [xout[1], 180]	#x range in which the graph is to be mapped to
	yout = [base - variance * base, base + variance * base]	#y range in which the graph is to be mapped to
	if t >= xout[0] and t < xout[1]:
		#print("sinx")
		xin = [0, 2 * math.pi]	#x range in which the template graph is
		yin = [-1, 1]	#y range in which the template graph is
		t = mapper(t, xout[0], xout[1], xin[0], xin[1]) #t comes in reference to the mapped graph, what would the t be for template graph? reverse map to get it
		ft = math.sin(t)	#determine the function value for the template graph
		x = mapper(t, xin[0], xin[1], xout[0], xout[1])	#get the mapped x value, this is only to get the corresponding y value
		y = mapper(ft, yin[0], yin[1], yout[0], yout[1])	#get the mapped y value
		return [x, y]
	#end if

	#y = x^2
	xout = [xout[1], 300]									#
	yout = [base - variance * base, base + variance * base]	#
	if t >= xout[0] and t < xout[1]:
		#print("x^2")
		xin = [-2, 2]										#
		yin = [0, 4]										#
		t = mapper(t, xout[0], xout[1], xin[0], xin[1])
		ft = t ** 2											#
		x = mapper(t, xin[0], xin[1], xout[0], xout[1])
		y = mapper(ft, yin[0], yin[1], yout[0], yout[1])
		return [x, y]
	#end if

	return [t+0, base]
#end def

def mapper(val, in1, in2, out1, out2):
	m = (out2 - out1) / (in2 - in1)
	c = out1 - m * in1
	y = m * val + c
	return y
#end def

def addMeter(dpid, meter_id, rate):
	payload = {
		"dpid": dpid,
		"flags": "KBPS",
		"meter_id": meter_id,
		"bands": [
			{
				"type": "DROP",
				"rate": rate,
				"burst_size": 0
			}
		]
	}
	headers = {
		'Content-Type': 'application/json'
	}
	payload = json.dumps(payload, indent = 4)
	res = rest.post("http://127.0.0.1:8080/stats/meterentry/add", data = payload, headers = headers)
# end def

def addFlow(dpid, udp_dst, meter_id):
	manageFlow(dpid, udp_dst, meter_id, "http://127.0.0.1:8080/stats/flowentry/add")
# end def

def deleteFlow(dpid, udp_dst, meter_id):
	manageFlow(dpid, udp_dst, meter_id, "http://127.0.0.1:8080/stats/flowentry/delete")
# end def

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
			{
				"type": "METER",
				"meter_id": meter_id
			},
			{
				"type": "OUTPUT",
				"port": 2
			}
		]
	}

	headers = {
		'Content-Type': 'application/json'
	}
	payload = json.dumps(payload, indent = 4)
	res = rest.post(url, data = payload, headers = headers)
# end def

def modifyMeter(dpid, meter_id, rate):
	payload = {
		"dpid": dpid,
		"flags": "KBPS",
		"meter_id": meter_id,
		"bands": [
			{
				"type": "DROP",
				"rate": rate,
				"burst_size": 0
			}
		]
	}
	headers = {
		'Content-Type': 'application/json'
	}
	payload = json.dumps(payload, indent = 4)
	res = rest.post("http://127.0.0.1:8080/stats/meterentry/modify", data = payload, headers = headers)
#end def

main()
