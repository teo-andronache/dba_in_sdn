#!/usr/bin/env python3
from ryu.base import app_manager
from ryu.controller import ofp_event
from ryu.controller.handler import CONFIG_DISPATCHER, MAIN_DISPATCHER, DEAD_DISPATCHER
from ryu.controller.handler import set_ev_cls
from ryu.ofproto import ofproto_v1_3
from ryu.lib.packet import packet, ethernet, ether_types, ipv4, tcp as tcp_proto
from ryu.lib import hub

class MaxMinFairSwitch13(app_manager.RyuApp):
    OFP_VERSIONS = [ofproto_v1_3.OFP_VERSION]

    # per-port link capacity in kbps
    LINK_CAPACITY = 100_000  

    # estimated RTT in seconds (for burst sizing)
    ESTIMATED_RTT = 0.010  

    # how often to recompute fair-share rates (s)
    FAIR_INTERVAL = 1  

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # map (dpid, ip_addr) -> mac_addr
        self.ip_to_mac     = {}
        # map dpid -> { mac_addr -> port_no }
        self.mac_to_port   = {}
        # map (dpid, src_ip, dst_ip, sport, dport) -> meter_id
        self.flow_to_meter = {}
        self.next_meter_id = 1
        self.datapaths     = {}
        # start background thread
        self.monitor_thread = hub.spawn(self._fair_rate_manager)

    @set_ev_cls(ofp_event.EventOFPStateChange, [MAIN_DISPATCHER, DEAD_DISPATCHER])
    def _state_change_handler(self, ev):
        dp = ev.datapath
        if ev.state == MAIN_DISPATCHER:
            self.datapaths[dp.id] = dp
        elif ev.state == DEAD_DISPATCHER:
            self.datapaths.pop(dp.id, None)

    @set_ev_cls(ofp_event.EventOFPSwitchFeatures, CONFIG_DISPATCHER)
    def _switch_features_handler(self, ev):
        dp     = ev.msg.datapath
        ofp    = dp.ofproto
        parser = dp.ofproto_parser

        # delete all existing meters & flows on this switch
        dp.send_msg(parser.OFPMeterMod(datapath=dp,
                                       command=ofp.OFPMC_DELETE,
                                       meter_id=ofp.OFPM_ALL))
        dp.send_msg(parser.OFPFlowMod(datapath=dp,
                                      command=ofp.OFPFC_DELETE,
                                      out_port=ofp.OFPP_ANY,
                                      out_group=ofp.OFPG_ANY))

        # purge in-memory entries for this dpid
        self.flow_to_meter = {k: v for k, v in self.flow_to_meter.items()
                              if k[0] != dp.id}

        # install table-miss entry
        match   = parser.OFPMatch()
        actions = [ parser.OFPActionOutput(ofp.OFPP_CONTROLLER,
                                           ofp.OFPCML_NO_BUFFER) ]
        self._add_flow(dp, priority=0, match=match, actions=actions)

    def _add_flow(self, dp, priority, match, actions,
                  buffer_id=None, meter_id=None):
        ofp    = dp.ofproto
        parser = dp.ofproto_parser
        inst   = []

        if meter_id:
            inst.append(parser.OFPInstructionMeter(meter_id))
        inst.append(parser.OFPInstructionActions(ofp.OFPIT_APPLY_ACTIONS, actions))

        if buffer_id:
            fm = parser.OFPFlowMod(datapath=dp,
                                   buffer_id=buffer_id,
                                   priority=priority,
                                   match=match,
                                   instructions=inst)
        else:
            fm = parser.OFPFlowMod(datapath=dp,
                                   priority=priority,
                                   match=match,
                                   instructions=inst)
        dp.send_msg(fm)

    @set_ev_cls(ofp_event.EventOFPPacketIn, MAIN_DISPATCHER)
    def _packet_in_handler(self, ev):
        msg    = ev.msg
        dp     = msg.datapath
        ofp    = dp.ofproto
        parser = dp.ofproto_parser
        in_port = msg.match['in_port']

        pkt = packet.Packet(msg.data)
        eth = pkt.get_protocol(ethernet.ethernet)
        if eth.ethertype == ether_types.ETH_TYPE_LLDP:
            return

        dpid = dp.id
        # learn MAC->port
        self.mac_to_port.setdefault(dpid, {})[eth.src] = in_port

        # if IP packet, learn IP->MAC
        ip_pkt = pkt.get_protocol(ipv4.ipv4)
        if ip_pkt:
            self.ip_to_mac[(dpid, ip_pkt.src)] = eth.src

        # decide out port
        out_port = self.mac_to_port[dpid].get(eth.dst, ofp.OFPP_FLOOD)

        # build match for flow install
        match = parser.OFPMatch(in_port=in_port,
                                eth_src=eth.src,
                                eth_dst=eth.dst)

        # only meter genuine TCP flows
        meter_id = None
        tcp_pkt = pkt.get_protocol(tcp_proto.tcp)
        if ip_pkt and tcp_pkt and out_port != ofp.OFPP_FLOOD:
            key = (dpid, ip_pkt.src, ip_pkt.dst,
                   tcp_pkt.src_port, tcp_pkt.dst_port)
            if key not in self.flow_to_meter:
                meter_id = self.next_meter_id
                self.next_meter_id += 1
                self._install_meter(dp, meter_id, self.LINK_CAPACITY)
                self.flow_to_meter[key] = meter_id
            else:
                meter_id = self.flow_to_meter[key]

        actions = [ parser.OFPActionOutput(out_port) ]

        # install the flow directing through the meter (if any)
        if out_port != ofp.OFPP_FLOOD:
            if msg.buffer_id != ofp.OFP_NO_BUFFER:
                self._add_flow(dp, 1, match, actions,
                               buffer_id=msg.buffer_id,
                               meter_id=meter_id)
                return
            else:
                self._add_flow(dp, 1, match, actions, meter_id=meter_id)

        # fallback: immediate packet_out
        data = None
        if msg.buffer_id == ofp.OFP_NO_BUFFER:
            data = msg.data
        out = parser.OFPPacketOut(datapath=dp,
                                  buffer_id=msg.buffer_id,
                                  in_port=in_port,
                                  actions=actions,
                                  data=data)
        dp.send_msg(out)

    def _install_meter(self, dp, meter_id, rate_kbps):
        ofp    = dp.ofproto
        parser = dp.ofproto_parser
        burst  = int(rate_kbps * self.ESTIMATED_RTT)
        bands  = [ parser.OFPMeterBandDrop(rate=rate_kbps,
                                           burst_size=burst) ]
        mod    = parser.OFPMeterMod(datapath=dp,
                                   command=ofp.OFPMC_ADD,
                                   flags=ofp.OFPMF_KBPS,
                                   meter_id=meter_id,
                                   bands=bands)
        dp.send_msg(mod)

    def _modify_meter(self, dp, meter_id, new_rate_kbps):
        ofp    = dp.ofproto
        parser = dp.ofproto_parser
        burst  = int(new_rate_kbps * self.ESTIMATED_RTT)
        bands  = [ parser.OFPMeterBandDrop(rate=new_rate_kbps,
                                           burst_size=burst) ]
        mod    = parser.OFPMeterMod(datapath=dp,
                                   command=ofp.OFPMC_MODIFY,
                                   flags=ofp.OFPMF_KBPS,
                                   meter_id=meter_id,
                                   bands=bands)
        dp.send_msg(mod)

    def _lookup_out_port(self, dpid, dst_ip):
        """
        Given switch dpid and destination IP, return learned output port,
        or None if unknown.
        """
        mac  = self.ip_to_mac.get((dpid, dst_ip))
        if mac is None:
            return None
        return self.mac_to_port.get(dpid, {}).get(mac)

    def _fair_rate_manager(self):
        """Recompute and push true max-min fair rates once per interval."""
        while True:
            hub.sleep(self.FAIR_INTERVAL)

            for dp in list(self.datapaths.values()):
                # 1) bucket each flow by its egress port
                port_buckets = {}   # port_no -> list of (flow_key, meter_id)
                for flow_key, meter_id in list(self.flow_to_meter.items()):
                    dpid = flow_key[0]
                    if dpid != dp.id:
                        continue
                    # find output port
                    _, _, dst_ip, _, _ = flow_key
                    out_port = self._lookup_out_port(dpid, dst_ip)
                    if out_port is None:
                        continue
                    port_buckets.setdefault(out_port, []).append((flow_key, meter_id))

                # 2) for each port run water-filling across its flows
                for port, flows in port_buckets.items():
                    # total capacity of this port
                    C = self.LINK_CAPACITY
                    # build list of (flow_key, meter_id, demand)
                    fl = []
                    for flow_key, m_id in flows:
                        # default to infinite if no entry
                        demand = self.flow_demand.get(flow_key, float('inf'))
                        fl.append([flow_key, m_id, demand, None])  # last slot = allocation

                    # sort by increasing demand
                    fl.sort(key=lambda x: x[2])

                    n = len(fl)
                    remaining = n
                    used = 0

                    # water-fill
                    for i, entry in enumerate(fl):
                        demand = entry[2]
                        share = (C - used) / remaining
                        alloc = min(demand, share)
                        entry[3] = alloc
                        used += alloc
                        remaining -= 1

                    # 3) push allocations into meters
                    for flow_key, m_id, _, alloc in fl:
                        self._modify_meter(dp, m_id, int(alloc))
