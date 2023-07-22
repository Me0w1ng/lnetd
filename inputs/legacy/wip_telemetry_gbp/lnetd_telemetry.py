from google.protobuf import text_format

import socket
import struct
import threading
from thread import start_new_thread
import logging
import time
import sys
import json
import datetime
from kafka import SimpleProducer, KafkaClient
sys.dont_write_bytecode = True

import telemetry_pb2 #cisco
import ifstatsbag_generic_pb2 # cisco interface stats
import im_cmd_info_pb2 #cisco interface info 
import telemetry_top_pb2,logical_port_pb2 # juniper
import snmp_agen_oper_if_index_pb2 # cisco snmp ifindex

from gbp_parse_msg import * #create kafka message and write it 

verbose = 2
kafka_msg = False
influx_msg = True
#move this to anothe module
from influxdb import InfluxDBClient
client = InfluxDBClient(host='127.0.0.1', port=8086, database='telemetry')
#kafka
#kafka = KafkaClient('127.0.0.1:9092')
#producer = SimpleProducer(kafka)

def decode_cisco_msg_tcp(msg):
	header = msg.recv(12) #header 
	msg_type, encode_type, msg_version, flags, msg_length = struct.unpack('>hhhhi',header)
	msg_data = b''
	print encode_type
        msg.send('ACK!')
        msg.close()
        '''
	if encode_type == 1:
		while len(msg_data) < msg_length:
			msg_data += msg.recv(msg_length - len(msg_data))
		gpb_parser = telemetry_pb2.Telemetry()
		gpb_data = gpb_parser.ParseFromString(msg_data)
		if gpb_parser.encoding_path == 'Cisco-IOS-XR-infra-statsd-oper:infra-statistics/interfaces/interface/latest/generic-counters':
			row_key = ifstatsbag_generic_pb2.ifstatsbag_generic_KEYS()
			row_data = ifstatsbag_generic_pb2.ifstatsbag_generic()
			for new_row in gpb_parser.data_gpb.row:
				row_data.ParseFromString(new_row.content)
				row_key.ParseFromString(new_row.keys)
				if kafka_msg:
					kafka_msg_parse = create_kafka_message(gpb_parser.encoding_path,gpb_parser.node_id_str,row_key,row_data)
					producer.send_messages(b'ios_xr_interface_counters',kafka_msg_parse)
					logging.info('Write {} to kafka topic'.format(gpb_parser.encoding_path))
				elif influx_msg:
					influx_msg_parse = create_influx_message(gpb_parser.encoding_path,gpb_parser.node_id_str,row_key,row_data)
					client.write_points([influx_msg_parse],time_precision = 's')
                                        logging.info('Write {} to InfluxDB'.format(gpb_parser.encoding_path))
				else:
					print ('Row_key:{}\n,Row_data:{}').format(row_key,row_data)
		elif gpb_parser.encoding_path == 'Cisco-IOS-XR-pfi-im-cmd-oper:interfaces/interface-xr/interface':
			row_key = ifstatsbag_generic_pb2.ifstatsbag_generic_KEYS()
			row_data = im_cmd_info_pb2.im_cmd_info()
			for new_row in gpb_parser.data_gpb.row:
				row_data.ParseFromString(new_row.content)
				row_key.ParseFromString(new_row.keys)
				#print row_data
				if kafka_msg:
					kafka_msg_parse = create_kafka_message(gpb_parser.encoding_path,gpb_parser.node_id_str,row_key,row_data)
					producer.send_messages(b'ios_xr_interface_info',kafka_msg_parse)
					logging.info('Write {} to kafka topic'.format(gpb_parser.encoding_path))
				elif influx_msg:
					influx_msg_parse = create_influx_message(gpb_parser.encoding_path,gpb_parser.node_id_str,row_key,row_data)
                                        client.write_points([influx_msg_parse],time_precision = 's')
                                        logging.info('Write {} to InfluxDB'.format(gpb_parser.encoding_path))
				else:
					print ('Row_key:{}\n,Row_data:{}').format(row_key,row_data)
		elif gpb_parser.encoding_path == 'Cisco-IOS-XR-snmp-agent-oper:snmp/if-indexes/if-index':
			row_data = snmp_agen_oper_if_index_pb2.snmp_ifindex_ifname()
			row_key = snmp_agen_oper_if_index_pb2.snmp_ifindex_ifname_KEYS()
			for new_row in gpb_parser.data_gpb.row:
				row_data.ParseFromString(new_row.content)
				row_key.ParseFromString(new_row.keys)
				if kafka_msg:
					kafka_msg_parse = create_kafka_message(gpb_parser.encoding_path,gpb_parser.node_id_str,row_key,row_data)
					producer.send_messages(b'ios_xr_interface_snmp',kafka_msg_parse)
					logging.info('Write {} to kafka topic'.format(gpb_parser.encoding_path))
				elif influx_msg:
					influx_msg_parse = create_influx_message(gpb_parser.encoding_path,gpb_parser.node_id_str,row_key,row_data)
                                        client.write_points([influx_msg_parse],time_precision = 's')
                                        logging.info('Write {} to InfluxDB'.format(gpb_parser.encoding_path))
				else:
					print ('Row_key:{}\n,Row_data:{}').format(row_key,row_data)
		else:
			print 'No support for this path yet'
        '''
	return 0
def decode_jnp_msg_udp(msg):
	gpb_parser = telemetry_top_pb2.TelemetryStream()
	gpb_parser.ParseFromString(msg)
	if gpb_parser.sensor_name == 'LOGICAL-INTERFACE-SENSOR:/junos/system/linecard/interface/logical/usage/:/junos/system/linecard/interface/logical/usage/:PFE':
		hostname = gpb_parser.system_id.split(':')[0]
		jnpr_ext = gpb_parser.enterprise.Extensions[telemetry_top_pb2.juniperNetworks]
		ports = jnpr_ext.Extensions[logical_port_pb2.jnprLogicalInterfaceExt]
		for port in ports.interface_info :
			if kafka_msg:
				kafka_msg_parse = create_kafka_message(gpb_parser.sensor_name,hostname,'',port)
				producer.send_messages(b'jnp_interface_stats',kafka_msg_parse)
				logging.info('Write {} to kafka topic'.format(gpb_parser.sensor_name))
			elif influx_msg:
				influx_msg_parse = create_influx_message(gpb_parser.sensor_name,hostname,'',port)
				client.write_points([influx_msg_parse])
			else:
				print ('Row_key:{}\n,Row_data:{}').format('',port)
	else:
		print 'No support for this path yet'

def udp_rcv_message(verbose=verbose):
	while True:
		msg , address = udp_sock.recvfrom(2**16)
		#print address
		if verbose == 1:
			logging.info('UDP message received')
		elif verbose == 2:
			logging.debug('UDP message received from : %s' %address[0])
		try:
			#while True:
			decode_jnp_msg_udp(msg)
		except Exception as e:
			print("ERROR: Failed to get UDP message. Attempting to reopen connection: {}".format(e))

def tcp_rcv_message(verbose=verbose):
	#while True:
        msg , address = tcp_sock.accept()
	'''
	if verbose == 1:
			logging.info('TCP message received')
		elif verbose == 2:
			logging.debug('TCP message received from : %s' %address[0])
		try:
			while True:
                            threading.Thread(target = decode_cisco_msg_tcp,args = (msg,)).start()
		        #start_new_thread(decode_cisco_msg_tcp,(msg,))
		except Exception as e:
			print("ERROR: Failed to get TCP message. Attempting to reopen connection: {}".format(e))
        '''
        print 'Accepted connection from {}:{}'.format(address[0], address[1])
        client_handle = threading.Thread(target = decode_cisco_msg_tcp,args = (msg,))
        client_handle.daemon = True
        client_handle.start()
def main():
	global tcp_sock,udp_sock
	logging.basicConfig(format='%(asctime)s %(message)s' , level=logging.INFO)
	socket_type = socket.AF_INET
	#bind udp 
	udp_sock = socket.socket(socket_type, socket.SOCK_DGRAM)
	udp_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
	udp_sock.bind(('77.246.57.149', 50010))
	#udp_sock.bind((args.ip_address, args.port))

	udp_thread = threading.Thread(target=udp_rcv_message)
	udp_thread.daemon = True
	udp_thread.start()
	#bind tcp 
	tcp_sock = socket.socket(socket_type)
	tcp_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
	tcp_sock.bind(('77.246.57.149', 50010))
	tcp_sock.listen(20)

	# this will come later , static for now  
	#udp_sock.bind((args.ip_address, args.port))

	#start a thread for tcp 
	tcp_thread = threading.Thread(target=tcp_rcv_message)
	tcp_thread.daemon = True
	tcp_thread.start()
	logging.info('LnetD Telemetry Collector...waiting for telemetry data')
	done = False
	while not done:
	    try:
	        time.sleep(60)
	    except KeyboardInterrupt:
	        done = True

if __name__ == '__main__':
	main()
