import asyncio
import copy
import random
import time

from pymodbus.client import (
    AsyncModbusSerialClient,
    AsyncModbusTcpClient
)

from .data_types import DataConverter
from .mqtt_client import MqttClient
from .globals import logger, deamon_opts


class ModbusStats:
    def __init__(self, writes_total:int=0, writes_error:int=0, reads_total:int=0, reads_error:int=0, timestamp:float=None):
        self.writes_total = writes_total
        self.writes_error = writes_error
        self.reads_total = reads_total
        self.reads_error = reads_error
        self.timestamp = timestamp if timestamp!=None else time.monotonic()
        
    def snapshot(self):
        snap = copy.copy(self)
        snap.timestamp = time.monotonic()
        return snap
    
    def diff_stat(self, old_snap):
        return(ModbusStats(
                writes_total=self.writes_total-old_snap.writes_total, 
                writes_error=self.writes_error-old_snap.writes_error, 
                reads_total=self.reads_total-old_snap.reads_total, 
                reads_error=self.reads_error-old_snap.reads_error, 
                timestamp=self.timestamp-old_snap.timestamp
            ))
 

class ModbusMaster:

    #==================================================================================================================
    #
    # Class methods and attributes
    #

    all_modbus_master = list()

    @classmethod
    def new_modbus_rtu_master(cls, rtu_dev:str, rtu_parity:str, rtu_baud:int, modbus_timeout:int) -> 'ModbusMaster' :
        if rtu_parity == "none":
            parity = "N"
        if rtu_parity == "odd":
            parity = "O"
        if rtu_parity == "even":
            parity = "E"
        master = AsyncModbusSerialClient(port=rtu_dev, stopbits=1, bytesize=8, parity=parity, baudrate=rtu_baud, timeout=modbus_timeout)
        return cls(master)

    @classmethod
    def new_modbus_tcp_master(cls, tcp_host:str, tcp_port:int) -> 'ModbusMaster' :
        master = AsyncModbusTcpClient(tcp_host, port=tcp_port)
        return cls(master)


    #==================================================================================================================
    #
    # Instance methods
    #

    def __init__(self, master):
        self.master = master
        self.devices = list()
        self.runtask = None
        ModbusMaster.all_modbus_master.append(self)
        self.modbuslock = asyncio.Lock()
        self.stats = ModbusStats()
        self.stats_last = None


    async def write_to_slave(self, fct_code_write:int, write_reg, value, slaveid):
        result = None
        try:     
            await self.modbuslock.acquire()
            if fct_code_write == 5:
                if not isinstance(value,list) :
                    result = await self.master.write_coil(write_reg, value, slave=slaveid)
                else:
                    result = await self.master.write_coils(write_reg, value, slave=slaveid)
            elif fct_code_write == 6 :
                if not isinstance(value,list) and deamon_opts['avoid-fc6'] :
                    value = [ value ]
                if not isinstance(value,list) :
                    result = await self.master.write_register(write_reg, value, slave=slaveid)
                else:
                    result = await self.master.write_registers(write_reg, value, slave=slaveid)
            if result!=None and result.isError() :
                raise Exception(f'Error response from Modbus write call: {result.function_code}')
        except Exception as e:
            self.stats.writes_error += 1
            raise e
        finally:
            self.modbuslock.release()
            self.stats.writes_total += 1
    

    async def read_from_slave(self, function_code:int, start_reg:int, len_regs:int, slaveid:int):
        result = None
        try:
            await self.modbuslock.acquire()
            if function_code == 3:
                result = await self.master.read_holding_registers(start_reg, len_regs, slave=slaveid)
                data = result.registers if not result.isError() else None
            elif function_code == 1:
                result = await self.master.read_coils(start_reg, len_regs, slave=slaveid)
                data = result.bits if not result.isError() else None
            elif function_code == 2:
                result = await self.master.read_discrete_inputs(start_reg, len_regs, slave=slaveid)
                data = result.bits if not result.isError() else None
            elif function_code == 4:
                result = await self.master.read_input_registers(start_reg, len_regs, slave=slaveid)
                data = result.registers if not result.isError() else None
            if data == None:
                raise Exception(f'Error response from Modbus read call: {result.function_code}')
        except Exception as e:
            self.stats.reads_error += 1
            raise e
        finally:
            self.modbuslock.release()
            self.stats.reads_total += 1

        return data


    def run_workloop(self, task_group=None):
        #...........................................................................................
        async def workloop() -> None:
            try:
                while True:
                    if self.master.connected:
                        #logger.info(f'Modbus STILL connected')
                        await asyncio.sleep(2)
                        continue
                    logger.info(f'Connecting to Modbus')
                    await self.master.connect()
                    if self.master.connected:
                        for dev in self.devices:
                            dev.enable()
                        logger.info(f'Modbus connected successfully')
                    else:
                        for dev in self.devices:
                            dev.disable()
                        self.stats.reads_error += 1
                        self.stats.reads_total += 1
                        logger.info(f'Modbus NOT connected')
            except asyncio.exceptions.CancelledError as e:
                logger.debug(f'Modbus master task stopped ({self}).')
        #...........................................................................................
        self.runtask = task_group.create_task(workloop())

    def register_device(self, device:'Device') -> None:
        self.devices.append(device)

    def is_connected(self) -> bool:
        return self.master.connected
    
    def get_statistics(self):
        stats = self.stats.snapshot()
        stats_last = self.stats_last
        self.stats_last = stats
        return (stats, stats_last)
    

class ModbusWriter:
    
    def __init__(self, mqtt_client:MqttClient) -> None:
        self.mqtt_client = mqtt_client
        self.set_request_queue = asyncio.Queue()
        self.runtask = None

    def add_set_request(self,req_userdata, req_msg):
        #XXX Exception handling
        #XXX Warning if long queue
        self.set_request_queue.put_nowait((req_userdata, req_msg))

    def run_workloop(self, task_group):
        #...........................................................................................
        async def workloop():
            try:
                while True:
                    (req_userdata, req_msg) = await self.set_request_queue.get()
                    try:
                        short_topic = str(req_msg.topic).removeprefix(self.mqtt_client.get_topic_base()+'/')
                        topic_parts = short_topic.split('/')
                        device_name = topic_parts[0]
                        value_topic = topic_parts[-1]
                        if device_name == self.mqtt_client.clientid:
                            # Here go any device level subscriptions
                            pass
                        else:
                            the_dev:Device = Device.all_devices[device_name]
                            if the_dev is None:
                                logger.warning( f'Tried writing to unknown device {device_name} by MQTT topic {req_msg.topic}.')
                            else:
                                payload = str(req_msg.payload.decode("utf-8"))
                                await the_dev.write_to_device( payload, req_msg.topic, device_name, value_topic)
                    except Exception as e:
                        logger.error(f'Error handling MQTT set request: {e}')

                    self.set_request_queue.task_done()
            except asyncio.exceptions.CancelledError as e:
                logger.debug(f'Modbus writer task stopped ({self}).')
        #...........................................................................................
        self.runtask = task_group.create_task(workloop())


class Device:

    #==================================================================================================================
    #
    # Class methods and attributes
    #

    all_devices = dict()

    @classmethod
    def register_device(cls, device:'Device') -> None :
        if device.name in cls.all_devices:
            raise LookupError(f'Device "{device.name}" from {device.config_source} already exists.')
        device.mqttc.register_device_topics( device.name)
        cls.all_devices[device.name] = device


    #==================================================================================================================
    #
    # Instance methods
    #

    def __init__(self, config_source, mqttc:MqttClient, modbus_master:ModbusMaster, device_name:str, slaveid:int, ha_properties:dict=dict()):
        if device_name in Device.all_devices:
            raise LookupError(f'Device "{device_name}" from {config_source} already exists.')
        
        self.config_source = config_source
        self.mqttc = mqttc
        self.modbus_master = modbus_master
        self.name = MqttClient.clean_topic(device_name, is_single_part=True)
        self.slaveid = slaveid
        self.ha_properties = ha_properties

        self.stats = ModbusStats()
        self.stats_last = None
        self.last_poll_success = None
        self.consec_fail_cnt = 0

        self.references = dict()
        self.pollers = list()

        self.enabled = False # We will get enabled once the Modbus is up

        Device.register_device(self)
        self.modbus_master.register_device(self)

        logger.info(f'Added new device {self}')


    #------------------------------------------------------------------------------------------------------------------
    # Enabling / disabling
    #

    def disable(self) -> None :
        if self.enabled: # do not use the method is_ready_to_comm() here. Just look at our own status!
            self.mqttc.publish_device_availability(self.name, False)
        self.enabled = False

    def enable(self) -> None :
        if not self.enabled: # do not use the method is_ready_to_comm() here. Just look at our own status!
            self.mqttc.publish_device_availability(self.name, True)
        self.enabled = True

    def is_ready_to_comm(self) -> bool:
        return (self.modbus_master.is_connected() and self.enabled)
    

    def schedule_reenable(self, task_group):
        #...........................................................................................
        async def workloop(sleeptime) -> None :
            try:
                logger.info(f'Scheduled reenabling {self} in {sleeptime}s')
                await asyncio.sleep(sleeptime)
                self.enable()
            except asyncio.exceptions.CancelledError as e:
                logger.debug(f'Reenabler task stopped ({self}).')
        #...........................................................................................
        sleeptime = 120 # XXX Make this configurable
        self.reenable_task = task_group.create_task(workloop(sleeptime))
    

    #------------------------------------------------------------------------------------------------------------------
    # Registering
    #

    def register_poller( self, new_poller:'Poller') -> None :
        self.pollers.append( new_poller)

    def register_reference( self, new_ref:'Reference') -> None :
        if new_ref.topic in self.references:
            raise LookupError( f'Topic "{new_ref.topic}" from {new_ref.config_source} already exists in device "{self.name}"')
        self.mqttc.register_reference_topics( self.name, new_ref.topic, new_ref.is_writeable)
        self.references[new_ref.topic] = new_ref


    #------------------------------------------------------------------------------------------------------------------
    # Modbus related
    #
    
    def get_statistics(self):
        stats = self.stats.snapshot()
        stats_last = self.stats_last
        self.stats_last = stats
        return (stats, stats_last)


    def count_new_poll( self, was_successfull:bool, task_group):
        self.stats.reads_total += 1        
        if was_successfull:
            self.consec_fail_cnt = 0
            if was_successfull != self.last_poll_success :
                self.enable()
        else:
            self.stats.reads_error +=1
            self.consec_fail_cnt += 1
            if self.consec_fail_cnt == 3:
                self.disable()
                self.schedule_reenable(task_group)
                logger.info(f'Disable device {self} after {self.consec_fail_cnt} consequtive failures.')
        self.last_poll_success = was_successfull


    async def write_to_device(self, payload_str:str, full_topic:str, dev_topic, val_topic) -> None:
        the_ref:Reference = self.references[val_topic]
        if the_ref is None :
            logger.warning( f'Tried writing to unknown reference {val_topic} by MQTT topic {full_topic}.')
            return
        if not the_ref.is_writeable :
            logger.warning( f'Tried writing to read only reference {val_topic} by MQTT topic {full_topic}.')
            return

        try:
            value = the_ref.data_converter.str2mb( payload_str)
        except Exception as e:
            raise Exception(f'Error converting MQTT value "{payload_str}" from "{full_topic}" for writing to Modbus: {e}')

        self.stats.writes_total += 1
        fct_code_write = the_ref.poller.function_code_write
        try:
            result = await self.modbus_master.write_to_slave(fct_code_write, the_ref.write_reg, value, self.slaveid)
        except Exception as e:
            self.stats.writes_error += 1
            raise Exception(f'Error writing to Modbus (device:{self.name} topic:{full_topic}): {e}')

        if result!=None and result.isError():
            self.stats.writes_error += 1
            raise Exception(f'Error writing to Modbus (device:{self.name} topic:{full_topic}): {result}')
        
        # writing was successful => we can assume, that the corresponding state can be set and published
        if the_ref.is_readable:
            the_ref.publish_value( value)


    def __str__(self):
        return f'device: {self.name}, {self.config_source}'


class Poller:

    #==================================================================================================================
    #
    # Class methods and attributes
    #

    all_poller = list()


    #==================================================================================================================
    #
    # Instance methods
    #

    def __init__(self, config_source, device:Device, start_reg:int, len_regs:int, reg_type:str, poll_rate:int):
        self.config_source = config_source
        self.device = device
        self.runtask = None
        self.name = f'Poller-{len(Poller.all_poller)}'

        self.start_reg = start_reg
        self.len_regs = len_regs
        self.reg_type = reg_type
        self.poll_rate = poll_rate

        self.function_code = None
        self.function_code_write = None
        err_text = ''
        if self.reg_type == "holding_register":
            if self.len_regs > 123:  # applies to TCP, RTU should support 125 registers. But let's be safe.
                err_text = "Too many registers (max. 123)."
            else:
                self.function_code = 3
                self.function_code_write = 6  # preset single register
        elif self.reg_type == "coil":
            if self.len_regs > 2000:  # some implementations don't seem to support 2008 coils/inputs
                err_text = "Too many coils (max. 2000)."
            else:
                self.function_code = 1
                self.function_code_write = 5  # force single coil
        elif self.reg_type == "input_register":
            if self.len_regs > 123:
                err_text = "Too many registers (max. 123)."
            else:
                self.function_code = 4
        elif self.reg_type == "input_status":
            if self.len_regs > 2000:
                err_text = "Too many inputs (max. 2000)."
            else:
                self.function_code = 2
        else:
            err_text = f'Unknown function code "{reg_type}".'

        if self.function_code is None:
            raise ValueError( f'{err_text} Ignoring poller {self}.')

        self.refs_all_list = list()
        self.refs_readable_list = list()
        self.refs_writeable_list = list()

        Poller.all_poller.append( self)
        self.device.register_poller( self)

        logger.debug(f'Added poller {self}')


    def is_ready_to_comm(self) -> bool:
        return self.device.is_ready_to_comm()


    async def poll(self, task_group) -> None :
        try:
            data = await self.device.modbus_master.read_from_slave(self.function_code, self.start_reg, self.len_regs, self.device.slaveid)
        except Exception as e:
            self.device.count_new_poll( False, task_group)
            raise Exception( f'Error reading from Modbus ({self}): {e}')

        try:
            logger.debug(f'Read Modbus fc:{self.function_code}, ref:{self.start_reg}, len:{self.len_regs}, id:{self.device.slaveid} -> data:{data}')
            for ref in self.refs_readable_list:
                raw_val = data[ref.start_reg_relative : (ref.data_converter.reg_cnt+ref.start_reg_relative)]
                ref.publish_value(raw_val)
        except Exception as e:
            self.device.count_new_poll( False, task_group)
            raise Exception( f'Error publishing value from Modbus ({self}): {e}')

        self.device.count_new_poll( True, task_group)


    def run_workloop(self, task_group):
        #...........................................................................................
        async def workloop() -> None :
            try:
                while not self.is_ready_to_comm(): # Wait with our initial delay to be ready for communication
                    await asyncio.sleep(0.5)
                await asyncio.sleep(self.poll_rate*random.uniform(0, 1)) # Delay start for a random time to distribute bus usage a bit
                while True:
                    if not self.is_ready_to_comm(): # If we're unable to communicate, just wait a bit and give it another try
                        await asyncio.sleep(0.5)
                        continue
                    logger.debug(f'Polling... ({self}).')
                    try:
                        await self.poll(task_group)
                    except Exception as e:
                        logger.error(f'Error polling ({self}): {e}')
                    await asyncio.sleep(self.poll_rate)
            except asyncio.exceptions.CancelledError as e:
                logger.debug(f'Poller task stopped ({self}).')
        #...........................................................................................
        self.runtask = task_group.create_task(workloop())


    def register_reference(self, new_ref:'Reference') -> None :
        self.device.register_reference( new_ref)
        self.refs_all_list.append( new_ref)
        if new_ref.is_readable:
            self.refs_readable_list.append( new_ref)
        if new_ref.is_writeable:
            self.refs_writeable_list.append( new_ref)


    def __str__(self):
        return f'device/poller: {self.device.name}/{self.name}, {self.config_source}'


class Reference:

    _default_data_type_by_fc = {
         3:     "uint16",   # holding_register
         1:     "bool",     # coil
         4:     "uint16",   # holding_register
         2:     "bool",     # coil
    }

    #==================================================================================================================
    #
    # Instance methods
    #
    
    def __init__(self, config_source, mqttc:MqttClient, poller:Poller, topic:str, start_reg:int, write_reg:int,
                is_readable:bool, is_writeable:bool, data_type:str, scale:float, format_str:str, 
                hass_entity_type:str=None, ha_properties:dict=dict()):
        self.config_source = config_source
        self.mqttc = mqttc
        self.poller = poller
        self.topic = MqttClient.clean_topic(topic, is_single_part=True)
        self.start_reg = start_reg
        self.write_reg = write_reg
        self.is_readable = is_readable 
        self.is_writeable = is_writeable
        self.scale = scale
        self.format_str = format_str
        self.hass_entity_type = hass_entity_type
        self.ha_properties = ha_properties

        if self.start_reg == None:
            self.start_reg = self.poller.start_reg
            logger.warning(f'start-reg not given for "{self}". Assuming poller\'s start-reg.')
        self.start_reg_relative = self.start_reg-self.poller.start_reg
        if self.is_writeable and self.write_reg==None:
            self.write_reg = self.start_reg
        self.last_val = None
        self.last_val_time = 0

        if not data_type or data_type=="":
            data_type = Reference._default_data_type_by_fc[poller.function_code]
        self.data_converter = DataConverter( data_type)

        if self.is_writeable and self.poller.function_code_write is None:
            raise ValueError(f'Writing requested for non-writeable poller (discrete input or input register) at {self}')

        if self.start_reg not in range(self.poller.start_reg, self.poller.start_reg+self.poller.len_regs) or self.start_reg+self.data_converter.reg_cnt-1 not in range(self.poller.start_reg, self.poller.start_reg+self.poller.len_regs):
            raise ValueError(f'Registers out of range of associated poller at {self}')

        self.poller.register_reference( self)


    def publish_value(self, raw_val:list[int]) -> None:
        pub_val = self.data_converter.mb2py(raw_val)
        pub_time = time.monotonic()
        if self.scale:
            pub_val = pub_val * self.scale
        if self.format_str:
            pub_val = self.format_str % pub_val
        if self.last_val != pub_val or pub_time-self.last_val_time>=deamon_opts['publish-seconds']:
            self.mqttc.publish_reference_state(self.poller.device.name, self.topic, pub_val)
            self.last_val = pub_val
            self.last_val_time = pub_time


    def __str__(self):
        return f'device/reference: {self.poller.device.name}/{self.topic}, {self.config_source}'
