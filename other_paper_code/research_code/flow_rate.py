# Copyright (C) 2016 Nippon Telegraph and Telephone Corporation.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or
# implied.
# See the License for the specific language governing permissions and
# limitations under the License.

# future update:
# use the duration from packet to calculate the rates. the poll interval may not be so fine tuned.

from ryu.app import simple_switch_13
from ryu.controller import ofp_event
from ryu.controller.handler import MAIN_DISPATCHER, DEAD_DISPATCHER
from ryu.controller.handler import set_ev_cls
from ryu.lib import hub
import mysql.connector
from datetime import datetime
from datetime import timedelta
import time
import requests as rest
import json
import numpy as np
import math
from icecream import ic


class SimpleMonitor13(simple_switch_13.SimpleSwitch13):
	def __init__(self, *args, **kwargs):
		super(SimpleMonitor13, self).__init__(*args, **kwargs)

		# controller variables
		self.datapaths = {}
		self.monitor_thread = hub.spawn(self._monitor)

		# database
		self.db = ""

		# constants
		self.RATE_CONV = 1024
		self.FLOWS_TO_DISCARD = 6  # discard first n flows for variable initialization because flow arrives late
		self.TRIALS_PER_STAT = 5

		self.MIN_POCKET = 2 # min must be 2 so that a rate can be calculated
		self.MAX_POCKET = 30
		self.trial = 1
		self.ALGORITHM = ["predict"]
		self.POLL_INTVL = 1

		# counter variables
		self.ignore_first_trial = True
		self.flow_id = 0
		self.pocket = self.MIN_POCKET
		self.algo_index = 0
		self.update_counter_flag = 0

		# state variables
		self.start_time = -1
		self.flows_discarded = 0
		self.configured_meters = {}
		self.prev_flow2 = {}
		self.prev_flow3 = {}
		self.rate_queue2 = {}
		self.rate_queue3 = {}
		self.flow_time = []
		self.curnt_time = datetime.today()
	# end def


	@set_ev_cls(ofp_event.EventOFPStateChange, [MAIN_DISPATCHER, DEAD_DISPATCHER])
	def _state_change_handler(self, ev):
		datapath = ev.datapath
		if ev.state == MAIN_DISPATCHER:
			if datapath.id not in self.datapaths:
				self.logger.debug('register datapath: %016x', datapath.id)
				self.datapaths[datapath.id] = datapath
		elif ev.state == DEAD_DISPATCHER:
			if datapath.id in self.datapaths:
				self.logger.debug('unregister datapath: %016x', datapath.id)
				del self.datapaths[datapath.id]
	# end def


	def _monitor(self):
		num_pockets = sum([1 for x in range(self.MIN_POCKET, self.MAX_POCKET + 1) if x % 2 == 0])
		print(f"Test will take roughly {self.POLL_INTVL * (self.TRIALS_PER_STAT - self.trial + 1) * num_pockets * (5 * 60 + 20) / 60 / 60} hrs")

		self.db = self.prepareDB(self, create_table=False)
		while True:
			self.flow_id = int(time.time() * 1000)
			if not self.ignore_first_trial:
				self.insertFlowIdentifier(self.flow_id)
			for dp in self.datapaths.values():
				if dp.id == 2 or dp.id == 3:
					self._request_flow_stats(dp, port = 1)
			hub.sleep(self.POLL_INTVL)
	# end def


	def _request_flow_stats(self, datapath, port):
		self.logger.debug('send meter request: %016x', datapath.id)
		ofproto = datapath.ofproto
		parser = datapath.ofproto_parser
		cookie = cookie_mask = 0
		match = parser.OFPMatch()   #no match, get all
		req = parser.OFPFlowStatsRequest(datapath, 0, ofproto.OFPTT_ALL, ofproto.OFPP_ANY, ofproto.OFPG_ANY, cookie, cookie_mask, match)
		datapath.send_msg(req)
	# end def


	@set_ev_cls(ofp_event.EventOFPFlowStatsReply, MAIN_DISPATCHER)
	def flow_stats_reply_handler(self, ev):
		# prepare the event messages for processing
		if not self.prepareFlowEventMessages(ev):
			return

		# if all the algos have run, dont do any further processing
		if self.algo_index == len(self.ALGORITHM):
			print("Stop the capture")
			return

		# get the flow rates in the correct format in the queue and manage the queues
		flows = self.getCurrentFlowRates(ev)
		if not flows:
			return
		[prev_flow, current_flow] = flows

		# approximate the bw, this is needed for switch 2 only
		meter_rate = {}
		matrix = {}
		if ev.msg.datapath.id == 2:
			for ids in self.configured_meters:
				[meter_rate[ids], matrix[ids]] = self.approximateBandwidth(self.flow_time, self.rate_queue2[ids])
		if ev.msg.datapath.id == 2:
			self.modifyMeterRates(meter_rate)
		self.saveFlowsToDb(ev.msg.datapath.id, prev_flow, current_flow, meter_rate, matrix)
		self.updateFlowCounters(ev.msg.datapath.id)    # must be called after all results for a flow is saved to DB
	# end def


	def approximateBandwidth(self, time_s, rate):
		algo = self.ALGORITHM[self.algo_index]
		if algo == "reg_mid":
			[m, c, r2] = self.regression(self, time_s, rate, self.pocket)  # find the best fit line
			x = [time_s[0], time_s[-1]]  # using the first and last x value, find the corresponding y
			y = [m * x[0] + c, m * x[1] + c]
			y = (y[0] + y[1]) / 2
			return [y, r2]
		elif algo == "reg_end":
			[m, c, r2] = self.regression(self, time_s, rate, self.pocket)  # find the best fit line
			y = m * time_s[-1] + c  # get the last x value and find the corresponding y
			return [y, r2]
		elif algo == "reg_strt":
			[m, c, r2] = self.regression(self, time_s, rate, self.pocket)  # find the best fit line
			y = m * time_s[0] + c  # get the first x value and find the corresponding y
			return [y, r2]
		elif algo == "avg":
			avg = sum(rate) / self.pocket
			return [avg, 0]
		elif algo == "predict":
			[m, c, r2] = self.regression(self, time_s, rate, self.pocket)  # find the best fit line
			diff = time_s[1] - time_s[0]	# find the time difference between two polls
			next_poll = time_s[-1] + diff	# from the last value of x, add the time difference so it goes in future
			y = m * next_poll + c	# this y is the expected rate in the next poll
			if y < 0:
				y = 0
			return [y, m]
	# end def


	def modifyMeterRates(self, meter_rate):
		datapath = [dp for dp in self.datapaths.values() if dp.id == 2][0]
		ofproto = datapath.ofproto
		parser = datapath.ofproto_parser
		for ids in meter_rate:
			if meter_rate[ids] < 0:
				continue
			bands = []
			dropband = parser.OFPMeterBandDrop(rate = int(meter_rate[ids]), burst_size = 0)
			bands.append(dropband)
			request = parser.OFPMeterMod(datapath=datapath, command=ofproto.OFPMC_MODIFY, flags=ofproto.OFPMF_KBPS, meter_id=ids, bands=bands)
			datapath.send_msg(request)
	# end def


	@staticmethod
	def regression(self, x, y, n):
		xy = np.multiply(x, y)
		x2 = np.square(x)
		y2 = np.square(y)

		sum_x = sum(x)
		sum_y = sum(y)
		sum_x2 = sum(x2)
		sum_y2 = sum(y2)
		sum_xy = sum(xy)

		# find m and c
		c = (sum_y * sum_x2 - sum_x * sum_xy) / (n * sum_x2 - sum_x ** 2)
		m = (n * sum_xy - sum_x * sum_y) / (n * sum_x2 - sum_x ** 2)

		# find r2
		rtop = n * sum_xy - sum_x * sum_y
		rbot = math.sqrt((n * sum_x2 - sum_x ** 2) * (n * sum_y2 - sum_y ** 2))
		r2 = 1 if rbot == 0 else (rtop / rbot) ** 2

		return [m, c, r2]
	# end def


	def updateFlowCounters(self, dpid):
		if dpid != 2:
			return
		# to check if a trial session has ended, its when all the flows become zero
		update = False
		if self.update_counter_flag == 0:
			for ids in self.rate_queue2:
				rates = self.rate_queue2[ids]
				if rates[len(rates) - 1] > 0:  # all the rates must be <=0 to indicate the flow has stopped
					return					   # return if flow is still running
			self.update_counter_flag = 1    # if control reaches here, then all the flows must have been 0, end of one trial
			update = True
		# end if

		# update trial counters
		if self.update_counter_flag == 1 and update:
			if self.ignore_first_trial:
				self.ignore_first_trial = False
				return

			self.trial += 1
			if self.trial > self.TRIALS_PER_STAT:
				self.trial = 1
				self.pocket += 2
			if self.pocket > self.MAX_POCKET:
				self.pocket = 2
				self.algo_index += 1
			# end if
			update = False
		# end if

		# to check if another flow session has started, its when all the flows become non-zero
		if self.update_counter_flag == 1:
			all_num = True # assume all are non zero
			for ids in self.rate_queue2:
				rates = self.rate_queue2[ids]
				if rates[len(rates) - 1] <= 0:  # if any is zero
					all_num = False # then not all flows are non-zeros (some are still zero)
					break   # terminate
			if not all_num: # if some are still zero, return
				return
			self.update_counter_flag = 0    # at this point, all flows must be non-zero, set the flag to 0

			# reset the initial counters to force a fresh start of new flow
			self.curnt_time = datetime.today()
			self.start_time = -1
			self.flows_discarded = 0
			self.configured_meters = {}
		# end if
	# end def


	def saveFlowsToDb(self, dpid, prev_flow, current_flow, meter_rate, matrix):
		if self.update_counter_flag == 1:	# this is a critical section, flows are transitioning to new trial, let them
			return							# transition successfully before doing anything

		for ids in current_flow:
			flow = current_flow[ids]

			sql = """UPDATE flow SET """
			sql += f"""poll_interval = {self.POLL_INTVL},
			algo = '{self.ALGORITHM[self.algo_index]}',
			pocket = {self.pocket},
			trial = {self.trial},
			s{dpid}_byte_in = {flow.byte_count},
			s{dpid}_byte_in_diff = {flow.byte_count - prev_flow[ids].byte_count},
			s{dpid}_kbyte_in_rate = {(flow.byte_count - prev_flow[ids].byte_count) / self.RATE_CONV / self.POLL_INTVL},
			s{dpid}_kbit_in_rate = {(flow.byte_count - prev_flow[ids].byte_count) * 8 / self.RATE_CONV / self.POLL_INTVL},
			s{dpid}_duration = '{self.curnt_time + timedelta(hours=-12, seconds=(flow.duration_sec - self.start_time), milliseconds=(flow.duration_nsec / 1000 / 1000))}'"""
			if dpid == 2:
				sql += f"""\n,meter_rate = {meter_rate[ids]},
							matrix = {matrix[ids]}"""
			sql += f""" WHERE id = {self.flow_id} AND meter_id = {ids};"""

			try:
				conn = self.db.cursor()
				conn.execute(sql)
				self.db.commit()
			except Exception:
				sql = sql.replace("\t", " ")
				sql = sql.replace("\n", " ")
				sql = sql.replace("  ", " ")
				ic(sql)
				self.db.rollback()
				logfile = open("logs.txt", "a")
				logfile.write(sql)
				logfile.write("\n\n")
				logfile.close()
	# end def


	def prepareFlowEventMessages(self, ev):
		'''this function only initializes the control variables'''
		if not ev.msg.body:  # wait for flow stats to start coming
			return
		if self.flows_discarded != self.FLOWS_TO_DISCARD:   # discard first few flows
			self.flows_discarded += 1
			return
		if not self.configured_meters:  # get the meter numbers to know how many flows are there
			self.getMeterRates()
			meter_ids = [ids for ids in self.configured_meters] # for each meter, create a space to store flow details
			for i in meter_ids:
				self.prev_flow2[i] = [] # for prev flows
				self.prev_flow3[i] = []
				self.rate_queue2[i] = [] # for queue
				self.rate_queue3[i] = []
				self.flow_time = []		# for time
		if self.start_time == -1:  # to start the stat.duration_sec from 0
			self.start_time = ev.msg.body[0].duration_sec
			for flow in ev.msg.body:    # set the prev_flows for both switches
				if flow.priority == 2:
					if ev.msg.datapath.id == 2:
						self.prev_flow2[flow.instructions[0].meter_id] = flow
					elif ev.msg.datapath.id == 3:
						self.prev_flow3[flow.instructions[0].meter_id] = flow
			# end for
			meter_ids = [ids for ids in self.configured_meters]
			if not self.prev_flow2[meter_ids[0]] or not self.prev_flow3[meter_ids[0]]: # check if any prev_flow is not set
				self.start_time = -1    # if any is not set, set start_time to -1 so the control comes here again and sets the other prev_flow
				return
		# end if

		return True
	#end def


	def getCurrentFlowRates(self, ev):
		# get all the necessary variables
		meter_ids = [ids for ids in self.configured_meters]  # get all the meter ids
		dpid = ev.msg.datapath.id
		prev_flow_temp = self.prev_flow2 if dpid == 2 else self.prev_flow3 if dpid == 3 else []  # get the prev flow

		# create space to store prev and current flow
		prev_flow = {}
		current_flow = {}
		for i in meter_ids:
			prev_flow[i] = []
			current_flow[i] = []

		# perform a deep copy of the prev flow because its used later
		for ids in prev_flow_temp:
			prev_flow[ids] = prev_flow_temp[ids]

		# copy the current flow in the same format as prev_flow, doesnt matter which dpid it is, just copy
		for flow in ev.msg.body:
			if flow.priority == 2:
				current_flow[flow.instructions[0].meter_id] = flow

		# calculate the rate for each flow, append to the respective queue
		for ids in prev_flow:
			prv_flow = prev_flow[ids]
			cur_flow = current_flow[ids]
			rate = (cur_flow.byte_count - prv_flow.byte_count) * 8 / self.RATE_CONV / self.POLL_INTVL
			if dpid == 2:
				self.rate_queue2[ids].append(rate)
			if dpid == 3:
				self.rate_queue3[ids].append(rate)

		# get the duration of the flows, just get the details for any one flow and calculate time from that
		flow = self.prev_flow2[meter_ids[0]] if dpid == 2 else self.prev_flow3[meter_ids[0]] if dpid == 3 else []
		t = (flow.duration_sec - self.start_time) + (flow.duration_nsec / 1000 / 1000 / 1000)
		if dpid == 2:   # append just once
			self.flow_time.append(t)

		# update the prev_flow with the current one
		for ids in meter_ids:
			if dpid == 2:
				self.prev_flow2[ids] = current_flow[ids]
			if dpid == 3:
				self.prev_flow3[ids] = current_flow[ids]

		# make sure there is enough values in the queue
		for ids in meter_ids:
			if len(self.rate_queue2[ids]) < self.pocket or len(self.rate_queue3[ids]) < self.pocket:
				return

		# if there are more than required values in the queue, remove the old ones
		for ids in meter_ids:
			while len(self.rate_queue2[ids]) > self.pocket:
				self.rate_queue2[ids].pop(0)
			while len(self.rate_queue3[ids]) > self.pocket:
				self.rate_queue3[ids].pop(0)
		while len(self.flow_time) > self.pocket:
			self.flow_time.pop(0)

		return [prev_flow, current_flow]
	# end def


	def insertFlowIdentifier(self, row_id):
		if not self.configured_meters:
			return
		sql = """INSERT INTO flow(id, meter_id) VALUES\n"""
		for m_id in self.configured_meters:
			sql += f"""({row_id}, {m_id}),"""
		sql = sql[:-1] + ";"

		conn = self.db.cursor()
		conn.execute(sql)
		self.db.commit()
	#end def


	def getMeterRates(self):
		# update this function later to get the meter rates dynamically from the switch
		self.configured_meters[1] = 8000
		self.configured_meters[2] = 6000
		self.configured_meters[3] = 4000
		self.configured_meters[4] = 2000
	# end def


	@staticmethod
	def prepareDB(self, create_table):
		db = mysql.connector.connect(host="localhost", user="deo", password="KrishDeo1#", database="grafana")
		conn = db.cursor()
		if not create_table:
			return db
		conn.execute("""DROP TABLE IF EXISTS flow;""")
		conn.execute("""CREATE TABLE IF NOT EXISTS flow(
						id BIGINT UNSIGNED,
						meter_id TINYINT UNSIGNED,
						poll_interval TINYINT UNSIGNED,
						algo VARCHAR(8),
						pocket TINYINT UNSIGNED,
						trial TINYINT UNSIGNED,

						s2_byte_in BIGINT UNSIGNED,
						s2_byte_in_diff INT UNSIGNED,
						s2_kbyte_in_rate DECIMAL(8,3),
						s2_kbit_in_rate DECIMAL(8,3),
						s2_duration TIMESTAMP(6),

						s3_byte_in BIGINT UNSIGNED,
						s3_byte_in_diff INT UNSIGNED,
						s3_kbyte_in_rate DECIMAL(8,3),
						s3_kbit_in_rate DECIMAL(8,3),
						s3_duration TIMESTAMP(6),

						meter_rate DECIMAL(8,3),
						matrix DECIMAL(10,5),
						PRIMARY KEY (id, meter_id));""")
		return db
	# end def
