import sys
import json
import logging
import time
import yaml
import os
import ast

from paho.mqtt import client as mqtt

from pymodbus.client.sync import ModbusSerialClient as ModbusClient # rtu
# from pymodbus.client.sync import ModbusTcpClient as ModbusTCPClient # tcp_ip

import queue

class LRPollerSync:
    def __init__(self, dev_port):
        with open('/config/modbus/poller.yaml') as stream:
        # with open('poller.yaml') as stream:
            self.dev_port = dev_port
            self.write_q = queue.Queue()

            try:
                poller_yaml_file = yaml.safe_load(stream)
                self.slaves = []
                self.status = {}
                self.poller_status = ''
                self.dev_port = poller_yaml_file['device']
                self.mqtt_broker = poller_yaml_file['mqtt_broker']
                self.mqtt_port = poller_yaml_file['mqtt_port']
                self.client_id = 'modbus_poller'
                self.host_IP = '192.168.3.106' # tcp_ip
                self.username = ''
                self.passwd = ''
                self.timeout = 3
                self.baudrate = 9600
                self.stopbits = 1
                self.timerStart = time.time()
                self.timerEnd = time.time()
                self.parity = 'N'
                self.write_retry_count = 3                                  # number of write attempts when response error occurs
                self.read_retry_count = 3                                   # number of attempts to poll a slave device when there is an error or no response
                self.off_mode_duration = 120                                # slave device disconnect time from polling (in sec.)
                self.publish_time = 10
                if 'client_id' in poller_yaml_file.keys():
                    self.client_id = poller_yaml_file['client_id']
                if 'username' in poller_yaml_file.keys():
                    self.username = poller_yaml_file['username']
                if 'passwd' in poller_yaml_file.keys():
                    self.passwd = poller_yaml_file['passwd']
                if 'mb_timeout' in poller_yaml_file.keys():
                    self.timeout = poller_yaml_file['mb_timeout']
                if 'mb_baudrate' in poller_yaml_file.keys():
                    self.baudrate = poller_yaml_file['mb_baudrate']
                if 'mb_stopbits' in poller_yaml_file.keys():
                    self.stopbits = poller_yaml_file['mb_stopbits']
                if 'mb_parity' in poller_yaml_file.keys():
                    self.parity = poller_yaml_file['mb_parity']
                if 'write_retry_count' in poller_yaml_file.keys():
                    self.parity = poller_yaml_file['write_retry_count']
                if 'read_retry_count' in poller_yaml_file.keys():
                    self.parity = poller_yaml_file['read_retry_count']
                if 'off_mode_duration' in poller_yaml_file.keys():
                    self.parity = poller_yaml_file['off_mode_duration']
                if 'publish_time' in poller_yaml_file.keys():
                    self.parity = poller_yaml_file['publish_time']
                if poller_yaml_file['slaves']:
                    for s in poller_yaml_file['slaves']:
                        s['status'] = 'online'
                        s['write_retry'] = 0
                        s['read_retry'] = 0
                        s['off_mode_status'] = False
                        s['off_mode_start_time'] = 0
                        self.status[s['slave_id']] = {}
                        self.status[s['slave_id']]['current_state'] = '-'
                        self.status[s['slave_id']]['previous_state'] = '-'

                        for data_type in s['data']:
                            data_meta = s['data'][data_type]
                            count = data_meta['count']
                            if 'offset' not in data_meta:
                                data_meta['offset'] = 0
                            if data_type in ['discrete_inputs', 'coils']:
                                data_meta['current_state'] = [False] * count
                                data_meta['previous_state'] = [False] * count
                            elif data_type in ['holding_registers', 'input_registers']:
                                count = data_meta['count']
                                data_meta['current_state'] = [0] * count
                                data_meta['previous_state'] = [0] * count
                            else:
                                print('Wrong data type')

                        for t in s['topics']:
                            t_chunks = t.split('/')
                            func_code = t_chunks[2]
                            data_addr = int(t_chunks[3])
                            data_type = ''
                            if func_code == '01':
                                data_type = 'coils_state'
                            elif func_code == '02':
                                data_type = 'discrete_inputs'
                            elif func_code == '03':
                                data_type = 'holding_registers_state'
                            elif func_code == '04':
                                data_type = 'input_registers'
                            elif func_code in ['05','15']:
                                data_type = 'coils'
                            elif func_code in ['06', '16']:
                                data_type = 'holding_registers'

                            if data_type not in s['data']:
                                s['data'][data_type] = {}

                            if 'addresses' not in s['data'][data_type]:
                                s['data'][data_type]['addresses'] = []

                            s['data'][data_type]['addresses'].append(data_addr)


                        self.slaves.append(s)

                    # print(self.slaves)
                else:
                    while True:
                        loop = True
                        time.sleep(3)

                self.run_poller()
            except yaml.YAMLError as exc:
                pass
            # except:
            #     self.mqtt_client.publish('mb/status','error in main loop')
            #     raise

    def run_poller(self):
        # self.modbus_client = ModbusTCPClient(self.host_IP, port=502) # tcp_ip
        self.modbus_client = ModbusClient(method = 'rtu', port = self.dev_port, timeout = self.timeout, baudrate = self.baudrate, stopbits = self.stopbits, parity = self.parity) # rtu
        self.modbus_client.connect()
        print('modbus:Connected')

        #mqtt client
        if self.modbus_client.connect():
            self.mqtt_client = mqtt.Client(self.client_id)
            self.mqtt_client.username_pw_set(username = self.username, password = self.passwd)
            self.mqtt_client.on_message = self.on_message
            self.mqtt_client.on_disconnect = self.on_disconnect
            self.mqtt_client.on_connect = self.on_connect


            self.mqtt_client.connect(self.mqtt_broker, port = self.mqtt_port)
            self.mqtt_client.loop_start()

            self.mqtt_client.publish('mb/status','init')

        # self.publish_all_states()

        while True:
            for s in self.slaves:
                if s['off_mode_status'] == False:
                    self.poll_slave(s)
                    # if s['status'] == 'offline':
                    #     if s['read_retry'] >= self.read_retry_count:
                    #         s['off_mode_status'] = True
                    #         s['read_retry'] = 0
                    #         s['off_mode_start_time'] = time.time()
                    #         print('slave_id: ' + str(s['slave_id']) + ', OFF MODE: on')
                    #     else:
                    #         self.poll_slave(s)
                    # else:
                    #     self.poll_slave(s)
                else:
                    if time.time() - s['off_mode_start_time'] > self.off_mode_duration:
                        print('slave_id: ' + str(s['slave_id']) + ', OFF MODE: off')
                        s['off_mode_status'] = False
                        s['read_retry'] = 0

                #checks if anything there to write
                self.check_for_write()

            if self.timerEnd - self.timerStart >= self.publish_time:
                self.publish_all_states()
                # print('publish_all_states activated')
                self.timerStart = time.time()
                self.timerEnd = time.time()
            else:
                self.timerEnd = time.time()



    def poll_slave(self, slave):
        # print('poll_slave')
        for fcode in slave['data']:
            if fcode == 'discrete_inputs':
                self.read_discrete_inputs(slave)
            elif fcode == 'input_registers':
                self.read_input_registers(slave)
            elif fcode == 'coils_state':
                self.read_coils(slave)
            elif fcode == 'holding_registers_state':
                self.read_holding_registers(slave)
            time.sleep(0.05)

    def publish_all_states(self):
        # print('publish_all_states')
        for s in self.slaves:
            if 'discrete_inputs' in s['data']:
                discrete_inputs = s['data']['discrete_inputs']
                for index, address in enumerate(discrete_inputs['addresses']):
                    topic  = 'mb/{}/{}/{}'.format(s['slave_id'], '02', address)
                    value = discrete_inputs['current_state'][index]
                    self.mqtt_client.publish(topic, ('OFF','ON')[value])
            if 'coils_state' in s['data']:
                coils_state = s['data']['coils_state']
                coils = s['data']['coils']
                for index, address in enumerate(coils_state['addresses']):
                    topic  = 'mb/{}/{}/{}'.format(s['slave_id'], '01', address)
                    value = coils['current_state'][index]
                    self.mqtt_client.publish(topic, ('OFF','ON')[value])
            if 'input_registers' in s['data']:
                input_registers = s['data']['input_registers']
                for index, address in enumerate(input_registers['addresses']):
                    topic  = 'mb/{}/{}/{}'.format(s['slave_id'], '04', address)
                    value = input_registers['current_state'][index]
                    self.mqtt_client.publish(topic, str(value))
            if 'holding_registers_state' in s['data']:
                holding_registers_state = s['data']['holding_registers_state']
                holding_registers = s['data']['holding_registers']
                for index, address in enumerate(holding_registers_state['addresses']):
                    topic  = 'mb/{}/{}/{}'.format(s['slave_id'], '03', address)
                    value = holding_registers['current_state'][index]
                    self.mqtt_client.publish(topic, str(value))

            # send current status of each slave
            self.mqtt_client.publish('mb/{}/status'.format(s['slave_id']), self.status[s['slave_id']]['current_state'])

            self.poller_status = ''
            for s in self.status:
              self.poller_status += str(s)+(':off' if self.status[s]['current_state'] == 'offline' else '')+'|';

        # overall send status of poller state
        self.mqtt_client.publish('mb/status',self.poller_status)
        return

    def check_for_write(self):
        # print('check_for_write', self.write_q.empty())
        if self.write_q.empty():
            return False
        write_data = {}
        # { 'slave_id': slave_id, 'func_code': func_code, 'address': address, 'value': value }
        while not self.write_q.empty():
            write_req = self.write_q.get()
            # print('get from write_q', write_req)
            func_pair = (write_req['slave_id'], write_req['func_code'])
            # print('func_pair: ' + str(func_pair))
            if func_pair not in write_data:
                write_data[func_pair] = {}
            write_data[func_pair][write_req['address']] = write_req['value']
        # print('write_data:', str(write_data))

        for func_pair in write_data:
            if func_pair[1] == '05':
                for address, value in write_data[func_pair].items():
                    slave = self.get_slave(func_pair[0], '05', address)
                    if slave:
                        if slave['slave_id'] != 0:
                            if slave['write_retry'] >= self.write_retry_count:
                                slave['write_retry'] = 0
                                return
                    else:
                        return
                    self.write_coil(slave, address, value)
            elif func_pair[1] == '15':
                slave = self.get_slave(func_pair[0], '15', list(write_data[func_pair].keys())[0])
                if slave:
                    if slave['slave_id'] != 0:
                        if slave['write_retry'] >= self.write_retry_count:
                            slave['write_retry'] = 0
                            return
                else:
                    return
                self.write_coils(slave, write_data[func_pair])
            elif func_pair[1] == '06':
                for address, value in write_data[func_pair].items():
                    slave = self.get_slave(func_pair[0], '06', address)
                    if slave:
                        if slave['slave_id'] != 0:
                            if slave['write_retry'] >= self.write_retry_count:
                                slave['write_retry'] = 0
                                return
                    else:
                        return
                    self.write_register(slave, address, value)
            elif func_pair[1] == '16':
                slave = self.get_slave(func_pair[0], '16', list(write_data[func_pair].keys())[0])
                if slave:
                    if slave['slave_id'] != 0:
                        if slave['write_retry'] >= self.write_retry_count:
                            slave['write_retry'] = 0
                            return
                else:
                    return
                # print('if slave:', write_data[func_pair])
                self.write_registers(slave, write_data[func_pair])

    def get_slave(self, slave_id, func_code, address):
        # print('get_slave', slave_id, func_code, address)
        if slave_id == 0:
            if func_code != '06' or address != 150:
                print('get_slave returns None')
                return None
            return { 'slave_id': 0 }
        for s in self.slaves:
            if s['slave_id'] == slave_id:
                if func_code == '15':
                    for reg_type, reg_data in s['data'].items():
                        if reg_type == 'coils' and address >= reg_data['offset'] and address < reg_data['offset'] + reg_data['count']:
                            return s
                elif func_code == '16':
                    for reg_type, reg_data in s['data'].items():
                        if reg_type == 'holding_registers' and address >= reg_data['offset'] and address < reg_data['offset'] + reg_data['count']:
                            # print('func_code == 16:', s)
                            return s
        for s in self.slaves:
            if s['slave_id'] == slave_id:
                return s
        print('get_slave returns None')
        return None

    def read_coils(self, slave):
        # print('read_coils')
        coils_data = slave['data']['coils']
        rr = self.modbus_client.read_coils(coils_data['offset'], coils_data['count'], unit = slave['slave_id'])
        if not rr.isError():
            temp_current_state = rr.bits
            current_state = temp_current_state[0:coils_data['count']]
            self.update_status(slave['slave_id'],'online')
            self.detect_and_publish_changes(slave, current_state, '01', 'coils_state')
            coils_data['previous_state'] = coils_data['current_state']
            coils_data['current_state'] = current_state
            slave['status'] = 'online'
            slave['read_retry'] = 0
        else:
            print('Error reading coils in slave id ' + str(slave['slave_id']))
            self.update_status(slave['slave_id'],'offline')
            slave['status'] = 'offline'
            # slave['read_retry'] += 1
            # print('slave_id: ' + str(slave['slave_id']) + ', status: offline')
            # print('slave_id: ' + str(slave['slave_id']) + ', read retry: ' + str(slave['read_retry']))
        return

    def read_discrete_inputs(self, slave):
        # print('read_discrete_inputs')
        di_data = slave['data']['discrete_inputs']
        rr = self.modbus_client.read_discrete_inputs(di_data['offset'], di_data['count'], unit = slave['slave_id'])
        if not rr.isError():
            temp_current_state = rr.bits
            current_state = temp_current_state[0:di_data['count']]
            # print('read_discrete_inputs:', slave['slave_id'], current_state)
            self.update_status(slave['slave_id'], 'online')
            self.detect_and_publish_changes(slave, current_state, '02', 'discrete_inputs')
            di_data['previous_state'] = di_data['current_state']
            di_data['current_state'] = current_state
            if slave['alias'] == 'DIO':
                do = slave['data']['coils']
                do['previous_state'] = do['current_state']
                do['current_state'] = current_state[do['count']:]
            slave['status'] = 'online'
            slave['read_retry'] = 0
        else:
            print('Error reading discrete inputs in slave id ' + str(slave['slave_id']))
            self.update_status(slave['slave_id'],'offline')
            slave['status'] = 'offline'
            # slave['read_retry'] += 1
            # print('slave_id: ' + str(slave['slave_id']) + ', status: offline')
            # print('slave_id: ' + str(slave['slave_id']) + ', read retry: ' + str(slave['read_retry']))

    def read_holding_registers(self, slave):
        # print('read_holding_registers')
        hr_data = slave['data']['holding_registers']
        rr = self.modbus_client.read_holding_registers(hr_data['offset'], hr_data['count'], unit = slave['slave_id'])
        if not rr.isError():
            current_state = rr.registers
            self.update_status(slave['slave_id'],'online')
            self.detect_and_publish_changes(slave, current_state, '03', 'holding_registers_state')
            hr_data['previous_state'] = hr_data['current_state']
            hr_data['current_state'] = current_state
            slave['status'] = 'online'
            slave['read_retry'] = 0
        else:
            print('Error reading holding registers in slave id ' + str(slave['slave_id']))
            self.update_status(slave['slave_id'],'offline')
            slave['status'] = 'offline'
            # slave['read_retry'] += 1
            # print('slave_id: ' + str(slave['slave_id']) + ', status: offline')
            # print('slave_id: ' + str(slave['slave_id']) + ', read retry: ' + str(slave['read_retry']))

    def read_input_registers(self, slave):
        # print('read_input_registers')
        ir_data = slave['data']['input_registers']
        rr = self.modbus_client.read_input_registers(ir_data['offset'], ir_data['count'], unit = slave['slave_id'])
        if not rr.isError():
            current_state = rr.registers
            self.update_status(slave['slave_id'], 'online')
            self.detect_and_publish_changes(slave, current_state, '04', 'input_registers')
            ir_data['previous_state'] = ir_data['current_state']
            ir_data['current_state'] = current_state
            slave['status'] = 'online'
            slave['read_retry'] = 0
        else:
            print('Error reading input registers in slave id ' + str(slave['slave_id']))
            self.update_status(slave['slave_id'], 'offline')
            slave['status'] = 'offline'
            # slave['read_retry'] += 1
            # print('slave_id: ' + str(slave['slave_id']) + ', status: offline')
            # print('slave_id: ' + str(slave['slave_id']) + ', read retry: ' + str(slave['read_retry']))

    def write_coil(self, slave, address, value):
        # print('write_coil')
        rr = None
        rr = self.modbus_client.write_coil(address, value, unit = slave['slave_id'])
        print('write_coil', slave['slave_id'], address, value)
        if rr.isError():
            print('error writing coil ' + str(slave['slave_id']))
            self.update_status(slave['slave_id'],'offline')
            slave['status'] = 'offline'
            slave['write_retry'] += 1
            print('slave_id: ' + str(slave['slave_id']) + ', status: offline')
            print('slave_id: ' + str(slave['slave_id']) + ', write retry: ' + str(slave['write_retry']))
            self._write_to_queue( { 'slave_id': slave['slave_id'], 'func_code': '05', 'address':address, 'value':value } )
        else:
            slave['status'] = 'online'
            slave['write_retry'] = 0

    def write_register(self, slave, address, value):
        # print('write_register')
        rr = self.modbus_client.write_register(address, value, unit = slave['slave_id'])
        print('write register', slave['slave_id'], address, value)
        if rr.isError() and slave['slave_id'] != 0:
            print('error writing register')
            self.update_status(slave['slave_id'],'offline')
            slave['status'] = 'offline'
            slave['write_retry'] += 1
            print('slave_id: ' + str(slave['slave_id']) + ', status: offline')
            print('slave_id: ' + str(slave['slave_id']) + ', write retry: ' + str(slave['write_retry']))
            self._write_to_queue( { 'slave_id': slave['slave_id'], 'func_code': '06', 'address':address, 'value':value } )
        else:
            if slave['slave_id'] != 0:
                slave['status'] = 'online'
                slave['write_retry'] = 0

    def write_coils(self, slave, new_values):
        # print('write_coils')
        current_state = []
        current_state = slave['data']['coils']['current_state']
        start_addr = slave['data']['coils']['offset']
        temp_offset = start_addr

        for topic in slave['topics']:
            if topic.split('/')[2] == '15':
                if topic.split('/')[3] == '0' and temp_offset != 0:
                    temp_offset = 0
                    break

        for idx in new_values:
            current_state[idx - temp_offset] = new_values[idx]

        rr = self.modbus_client.write_coils(start_addr, current_state, unit = slave['slave_id'])
        print('write_coils:', slave['slave_id'], start_addr, current_state)
        if rr.isError():
            print('error writing coils with slave id ' + str(slave['slave_id']))
            self.update_status(slave['slave_id'],'offline')
            slave['status'] = 'offline'
            slave['write_retry'] += 1
            print('slave_id: ' + str(slave['slave_id']) + ', status: offline')
            print('slave_id: ' + str(slave['slave_id']) + ', write retry: ' + str(slave['write_retry']))
            for i in new_values:
                # print('putting into queue:', 'slave_id:', slave['slave_id'], 'func_code: 15', 'address:', i, 'value:', new_values[i])
                self._write_to_queue( { 'slave_id': slave['slave_id'], 'func_code': '15', 'address':i, 'value':new_values[i] } )
        else:
            slave['status'] = 'online'
            slave['write_retry'] = 0

    def write_registers(self, slave, new_values):
        # print('write_registers')
        current_state = []
        current_state = slave['data']['holding_registers']['current_state']
        start_addr = slave['data']['holding_registers']['offset']
        temp_offset = start_addr

        for topic in slave['topics']:
            if topic.split('/')[2] == '16':
                if topic.split('/')[3] == '0' and temp_offset != 0:
                    temp_offset = 0
                    break

        for idx in new_values:
            current_state[idx - temp_offset] = new_values[idx]

        rr = self.modbus_client.write_registers(start_addr, current_state, unit = slave['slave_id'])
        print('write_registers:', slave['slave_id'], start_addr, current_state)

        if rr.isError() and slave['slave_id'] != 0:
            print('error writing registers in slave id ' + str(slave['slave_id']))
            self.update_status(slave['slave_id'],'offline')
            slave['status'] = 'offline'
            slave['write_retry'] += 1
            print('slave_id: ' + str(slave['slave_id']) + ', status: offline')
            print('slave_id: ' + str(slave['slave_id']) + ', write retry: ' + str(slave['write_retry']))
            for i in new_values:
                # print('putting into queue:', 'slave_id:', slave['slave_id'], 'func_code: 16', 'address:', i, 'value:', new_values[i])
                self._write_to_queue( { 'slave_id': slave['slave_id'], 'func_code': '16', 'address':i, 'value':new_values[i] } )
        else:
            if slave['slave_id'] != 0:
                slave['status'] = 'online'
                slave['write_retry'] = 0

    def update_status(self, slave_id, status):
        # print('update_status', self.status)
        if slave_id != 0:
            self.status[slave_id]['current_state'] = status

            if self.status[slave_id]['previous_state'] != self.status[slave_id]['current_state']:
                print('status state not equal. slave id: '+str(slave_id)+', status: '+self.status[slave_id]['current_state'])
                self.status[slave_id]['previous_state'] = self.status[slave_id]['current_state']
                self.mqtt_client.publish('mb/{}/status'.format(slave_id), self.status[slave_id]['current_state']) #abz

    def detect_and_publish_changes(self, slave, current_state, func_code, data_type):
        data = slave['data'][data_type]
        # print('detect_and_publish_changes data: '+ str(data))
        previuos_state = []
        if data_type == 'coils_state':
            previous_state = slave['data']['coils']['previous_state']
        elif data_type == 'holding_registers_state':
            previous_state = slave['data']['holding_registers']['previous_state']
        else:
            previous_state = data['previous_state']

        # print(data)
        for index, address in enumerate(data['addresses']):
            if current_state[index] != previous_state[index]:
                topic  = 'mb/{}/{}/{}'.format(slave['slave_id'], func_code, address)
                if type(current_state[index]) == bool:
                    self.mqtt_client.publish(topic, ('OFF','ON')[current_state[index]])
                    # print('change detected: slave_id: '+str(slave['slave_id'])+', func_code: '+str(func_code)+', address: '+str(address)+', value: '+str(('OFF','ON')[current_state[address]]))
                elif type(current_state[index]) == int:
                    self.mqtt_client.publish(topic, str(current_state[index]))
                    # print('change detected: slave_id: '+str(slave['slave_id'])+', func_code: '+str(func_code)+', address: '+str(address)+', value: '+str(current_state[address]))

    def on_message(self, client, userdata, message):
        # print(message.topic)
        slave_id = None
        func_code = None
        address = None
        value = None
        ok = True
        t_chunks = message.topic.split('/')
        if t_chunks[1].isnumeric():
            slave_id = int(t_chunks[1])
        else:
            ok = False
        if len(t_chunks) > 3:
            func_code = t_chunks[2]
            if t_chunks[2].isnumeric():
                address = int(t_chunks[3])
            else:
                ok = False
        else:
            ok = False

        value = message.payload.decode('utf-8')

        # for s in self.slaves:
        #     if s['slave_id'] == slave_id or slave_id == 0:
        #         if ok != False:
        #             ok = True

        if ok:
            # print('write_q:', 'slave_id:', slave_id, 'func_code:', func_code, 'address:', address, 'value:', value)
            if func_code in ['05', '15']:
                if value == 'OFF' or value == 'ON':
                    self._write_to_queue( { 'slave_id':slave_id, 'func_code':func_code, 'address':address, 'value':value == 'ON' } )
                else:
                    print('invalid value for coils')
            elif func_code in ['06', '16']:
                try:
                    self._write_to_queue( { 'slave_id':slave_id, 'func_code':func_code, 'address':address, 'value':int(value) } )
                except ValueError:
                    print('invalid value for holding_registers')

    def on_disconnect(self, client, userdata, rc):
        if rc != 0:
            print('mqtt: Unexpected disconnection')

    def on_connect(self, client, userdata, flags, rc):
        print('mqtt:Connected, subscribing to mb/# ')
        self.mqtt_client.subscribe('mb/#')

    def _write_to_queue(self, value):
        self.write_q.put(value)
        # print('added to queue:', value)

# if __name__ == '__main__':
#     port = '/dev/ttyUSB0'
#     if len(sys.argv) > 1:
#         port = sys.argv[1]

#     lr_poller = LRPollerSync(port)
    port = sys.argv[1]
    lr_poller = LRPollerSync(port)

