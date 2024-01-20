import asyncio
import random
import time

from pymodbus.client import (
    AsyncModbusSerialClient,
    AsyncModbusTcpClient
)

from .data_types import DataConverter
from .mqtt_client import MqttClient
from .globals import logger, deamon_opts


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
        master = AsyncModbusTcpClient(tcp_host, port=tcp_port, client_id="modbus2mqtt", clean_session=False)
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

    def run_workloop(self, task_group=None):
        self.runtask = task_group.create_task(self._workloop())

    async def _workloop(self) -> None:
        try:
            while True:
                if self.master.connected:
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
                    logger.info(f'Modbus NOT connected')
        except asyncio.exceptions.CancelledError as e:
            logger.debug(f'Modbus master task stopped ({self}).')

    def register_device(self, device:'Device') -> None:
        self.devices.append(device)

    def is_connected(self) -> bool:
        return self.master.connected


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
        self.runtask = task_group.create_task(self._workloop())

    async def _workloop(self):
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


class Device:

    all_devices = dict()

    #==================================================================================================================
    #
    # Class methods and attributes
    #

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

        self.last_poll_status = None
        self.poll_count = 0
        self.error_count = 0
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
        if self.enabled: # do not use the method is_enabled() here. Just look at our own status!
            self.mqttc.publish_device_availability(self.name, False)
        self.enabled = False

    def enable(self) -> None :
        if not self.enabled: # do not use the method is_enabled() here. Just look at our own status!
            self.mqttc.publish_device_availability(self.name, True)
        self.enabled = True

    def is_enabled(self) -> bool:
        return (self.modbus_master.is_connected() and self.enabled)


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
    # Diagnostics
    #

    async def publish_diagnostics(self) -> None :
        error_perc = (self.error_count/self.poll_count)*100 if self.poll_count != 0 else 0
        self.mqttc.publish_device_diagnostics( self.name, self.poll_count, error_perc, self.error_count)
        self.poll_count = 0
        self.error_count = 0


    #------------------------------------------------------------------------------------------------------------------
    # Modbus related
    #

    def count_new_poll( self, was_successfull:bool):
        self.poll_count += 1
        
        if was_successfull != self.last_poll_status :
            self.mqttc.publish_device_availability(self.name, was_successfull)
        self.last_poll_status = was_successfull

        if was_successfull:
            self.consec_fail_cnt = 0
            self.enable()
        else:
            self.error_count += 1
            self.consec_fail_cnt += 1
            if self.consec_fail_cnt == 3:
                self.mqttc.publish_device_availability(self.name, False)
                #if globs.args.autoremove:
                #    globs.logger.info("Poller "+self.topic+" with Slave-ID "+str(self.slaveid)+" disabled (functioncode: "+str(
                #        self.functioncode)+", start reference: "+str(self.reference)+", size: "+str(self.size)+").")
                #    for p in pollers:  # also fail all pollers with the same slave id
                #        if p.slaveid == self.slaveid:
                #            p.failcounter = 3
                #            p.disabled = True
                #            globs.logger.info("Poller "+p.topic+" with Slave-ID "+str(p.slaveid)+" disabled (functioncode: "+str(
                #                p.functioncode)+", start reference: "+str(p.reference)+", size: "+str(p.size)+").")
                #self.disable()
                pass

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

        fct_code_write = the_ref.poller.function_code_write
        try:     
            time.sleep(0.002)
            if fct_code_write == 5:
                if not isinstance(value,list) :
                    result = await self.modbus_master.master.write_coil(the_ref.write_reg, value, slave=self.slaveid)
                else:
                    result = await self.modbus_master.master.write_coils(the_ref.write_reg, value, slave=self.slaveid)
            elif fct_code_write == 6 :
                if not isinstance(value,list) and deamon_opts['avoid-fc6'] :
                    value = [ value ]
                if not isinstance(value,list) :
                    result = await self.modbus_master.master.write_register(the_ref.write_reg, value, slave=self.slaveid)
                else:
                    result = await self.modbus_master.master.write_registers(the_ref.write_reg, value, slave=self.slaveid)
        except Exception as e:
            raise Exception(f'Error writing to Modbus (device:{self.name} topic:{full_topic}): {e}')

        if result.isError():
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


    def is_enabled(self) -> bool:
        return self.device.is_enabled()


    async def poll(self) -> None :
        result = None
        try:
            time.sleep(0.002)
            if self.function_code == 3:
                result = await self.device.modbus_master.master.read_holding_registers(self.start_reg, self.len_regs, slave=self.device.slaveid)
                data = result.registers if not result.isError() else None
            elif self.function_code == 1:
                result = await self.device.modbus_master.master.read_coils(self.start_reg, self.len_regs, slave=self.device.slaveid)
                data = result.bits if not result.isError() else None
            elif self.function_code == 2:
                result = await self.device.modbus_master.master.read_discrete_inputs(self.start_reg, self.len_regs, slave=self.device.slaveid)
                data = result.bits if not result.isError() else None
            elif self.function_code == 4:
                result = await self.device.modbus_master.master.read_input_registers(self.start_reg, self.len_regs, slave=self.device.slaveid)
                data = result.registers if not result.isError() else None

            if data is not None:
                logger.debug(f'Read Modbus fc:{self.function_code}, ref:{self.start_reg}, len:{self.len_regs}, id:{self.device.slaveid} -> data:{data}')
                self.device.count_new_poll( True)
                for ref in self.refs_readable_list:
                    raw_val = data[ref.start_reg_relative : (ref.data_converter.reg_cnt+ref.start_reg_relative)]
                    ref.publish_value(raw_val)
            else:
                logger.warning(f'Error response from Modbus call ({self}): {self.function_code}')
        except Exception as e:
            self.device.count_new_poll( False)
            raise Exception( f'Error reading from Modbus ({self}): {e}')


    def run_workloop(self, task_group):
        self.runtask = task_group.create_task(self._workloop())


    async def _workloop(self) -> None :
        while not self.is_enabled(): # Wait with our initial delay to be enabled
            await asyncio.sleep(0.5)
        await asyncio.sleep(self.poll_rate*random.uniform(0, 1)) # Delay start for a random time to distribute bus usage a bit
        try:
            while True:
                if not self.is_enabled(): # If we're disabled, just wait a bit and give it another try
                    await asyncio.sleep(0.5)
                    continue
                logger.debug(f'Polling... ({self}).')
                try:
                    await self.poll()
                except Exception as e:
                    logger.error(f'Error polling ({self}): {e}')
                await asyncio.sleep(self.poll_rate)
        except asyncio.exceptions.CancelledError as e:
            logger.debug(f'Poller task stopped ({self}).')


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
