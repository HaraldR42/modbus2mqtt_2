import ssl
import paho.mqtt.client as mqtt
import queue
import socket

from .globals import logger


class MqttClient:

    #==================================================================================================================
    #
    # Class methods and attributes
    #

    @classmethod
    def clean_topic( cls, topic:str, is_single_part:bool=False) -> str:
        if is_single_part :
            topic.replace('/', '')
        else:
            while topic != topic.replace('//', '/'): topic = topic.replace('//', '/')
        topic = topic.replace('+', '')
        topic = topic.replace('#', '')
        topic = topic.replace('$', '')
        return topic


    #==================================================================================================================
    #
    # Instance methods
    #

    def __init__(self, mqtt_host:str, mqtt_port:int, mqtt_clientid:str,
                 mqtt_user:str, mqtt_pass:str, mqtt_cacerts:str, mqtt_insecure:bool, mqtt_tls_version:str, 
                 topic_base:str, topic_hass_autodisco_base:str, retain_values:bool, mqtt_value_qos:int):
        self.mqtt_host = mqtt_host
        self.mqtt_port = mqtt_port
        self.mqtt_user = mqtt_user
        self.mqtt_pass = mqtt_pass
        self.mqtt_cacerts = mqtt_cacerts
        self.mqtt_insecure = mqtt_insecure
        self.mqtt_tls_version = mqtt_tls_version
        self.retain_values = retain_values
        self.mqtt_value_qos = mqtt_value_qos
        self.topic_base = MqttClient.clean_topic( topic_base.rstrip('/'))
        self.topic_hass_autodisco_base =  MqttClient.clean_topic( topic_hass_autodisco_base.rstrip('/'))
        self.clientid = MqttClient.clean_topic(mqtt_clientid, is_single_part=True)
        self.modbus_writer = None

        self.unique_topic_publish_list = list()
        self.unique_topic_subscribe_list = list()

        self._register_daemon_topics()

        self.mqc = mqtt.Client(client_id=self.clientid)
        self.mqc.on_connect = self.on_connect_callback
        self.mqc.on_disconnect = self.on_disconnect_callback
        self.mqc.on_message = self.on_message_callback
        self.mqc.on_log = self.on_log_callback
        self.mqc.will_set(self.get_topic_daemon_avail(), self.get_avail_message(False), qos=0, retain=True)
        if self.mqtt_user or self.mqtt_pass:
            self.mqc.username_pw_set(self.mqtt_user, self.mqtt_pass)
            cert_regs = ssl.CERT_NONE if self.mqtt_insecure else ssl.CERT_REQUIRED
            self.mqc.tls_set(ca_certs=self.mqtt_cacerts, certfile=None, keyfile=None,
                             cert_reqs=cert_regs, tls_version=self.mqtt_tls_version)
            if self.mqtt_insecure:
                self.mqc.tls_insecure_set(True)
        logger.debug("MQTT client created")

    def set_modbus_writer(self, modbus_writer):
        self.modbus_writer = modbus_writer

    def make_initial_connection(self) -> bool :
        # Only publish messages after the initial connection has been made. 
        # If it becomes disconnected later, then the offline buffer will store messages, but only after the intial connection was made.
        try:
            logger.info(f'Connecting to MQTT Broker: {self.mqtt_host}:{self.mqtt_port}')
            self.mqc.connect(self.mqtt_host, self.mqtt_port, 60)
            self.mqc.loop_start()
            logger.info('MQTT Loop started')
            return True
        except Exception as e:
            logger.error(f'Error connecting to MQTT broker: {self.mqtt_host}:{self.mqtt_port}: {e}')
            return False
    

    #------------------------------------------------------------------------------------------------------------------
    # Publish methods
    #

    def publish_daemon_availability(self, is_available:bool) -> None:
        self.mqc.publish(self.get_topic_daemon_avail(), self.get_avail_message(is_available), qos=1, retain=True)

    def publish_device_availability(self, device_name:str, is_available:bool) -> None:
        self.mqc.publish(self.get_topic_device_availability(device_name), self.get_avail_message(is_available), qos=1, retain=True)

    def publish_device_diagnostics(self, device_name:str, poll_count:int, error_percent:int, error_count:int) -> None:
        self.mqc.publish(self.get_topic_device_diag_pollcount(device_name), str(poll_count), qos=0, retain=False)
        self.mqc.publish(self.get_topic_device_diag_errrate(device_name), str(error_percent), qos=0, retain=False)
        self.mqc.publish(self.get_topic_device_diag_errtotal(device_name), str(error_count), qos=0, retain=False)

    def publish_reference_state(self, device_name:str, topic:str, value:str) -> None :
        publish_result = self.mqc.publish(f'{self.get_topic_reference_value(device_name,topic)}', value, qos=self.mqtt_value_qos, retain=self.retain_values)
        logger.debug(f'Published MQTT topic: {self.get_topic_reference_value(device_name,topic)} value: {value} RC: {publish_result.rc}')

    def publish_hass_autodiscovery_entity(self, rel_topic:str, value:str) -> None :
        publish_result = self.mqc.publish(f'{self.get_topic_hass_autoconfig(rel_topic)}', value, retain=True)
        logger.debug(f'Published hass autodiscovery: {self.get_topic_hass_autoconfig(rel_topic)} value: {value} RC: {publish_result.rc}')


    #------------------------------------------------------------------------------------------------------------------
    # Topic and message value methods
    #
    # Topic structure: 
    #
    #   Daemon topics:  
    #     - Publish:   <topic_base>/<clientId>/<value_topic>/<daemon_value>
    #     - Subscribe: <topic_base>/<clientId>/<set_topic>/<daemon_function>
    #
    #   Device topics:
    #     - Publish:   <topic_base>/<device>/<value_topic>/<reference>
    #     - Subscribe: <topic_base>/<device>/<set_topic>/<reference>
    #

    def get_topic_base(self) -> str : 
        return self.topic_base


    def _register_daemon_topics(self) -> None :
        self._register_unique_topic( self.get_topic_daemon_avail())

    def get_topic_daemon_value_base(self) -> str : 
        return f'{self.get_topic_base()}/{self.clientid}'
    def get_topic_daemon_sub_base(self) -> str : 
        return f'{self.get_topic_base()}/{self.clientid}/set'

    def get_topic_daemon_avail(self) -> str : 
        return f'{self.get_topic_daemon_value_base()}/connected'
    

    def register_device_topics( self, device_name:str) -> None :
        self._register_unique_topic( self.get_topic_device_availability(device_name))
        self._register_unique_topic( self.get_topic_device_diag_pollcount(device_name))
        self._register_unique_topic( self.get_topic_device_diag_errrate(device_name))
        self._register_unique_topic( self.get_topic_device_diag_errtotal(device_name))

    def get_topic_device_value_base(self, device_name:str) -> str : 
        return f'{self.get_topic_base()}/{device_name}'
    def get_topic_device_sub_base(self, device_name:str) -> str : 
        return f'{self.get_topic_base()}/{device_name}/set'

    def get_topic_device_availability(self, device_name:str) -> str:
        return f'{self.get_topic_device_value_base(device_name)}/connected'
    def get_topic_device_diag_pollcount(self, device_name:str) -> str:
        return f'{self.get_topic_device_value_base(device_name)}/diagnostics/poll_count'
    def get_topic_device_diag_errrate(self, device_name:str) -> str:
        return f'{self.get_topic_device_value_base(device_name)}/diagnostics/errors_percent'
    def get_topic_device_diag_errtotal(self, device_name:str) -> str:
        return f'{self.get_topic_device_value_base(device_name)}/diagnostics/errors_total'


    def register_reference_topics( self, device_name:str, ref_topic:str, is_writable:bool) -> None :
        self._register_unique_topic( self.get_topic_reference_value(device_name, ref_topic))
        if is_writable:
             self._register_unique_topic( self.get_topic_reference_subsciption(device_name, ref_topic), is_subsciption=True)
    
    def get_topic_reference_value_base(self, device_name:str) -> str : 
        return f'{self.get_topic_base()}/{device_name}/value'
    def get_topic_reference_sub_base(self, device_name:str) -> str : 
        return f'{self.get_topic_base()}/{device_name}/set'

    def get_topic_reference_value(self, device_name:str, ref_topic:str) -> str : 
        return f'{self.get_topic_reference_value_base(device_name)}/{ref_topic}'
    def get_topic_reference_subsciption(self, device_name:str, ref_topic:str) -> str : 
        return f'{self.get_topic_reference_sub_base(device_name)}/{ref_topic}'


    def register_hass_topics( self) -> None :
        self._register_unique_topic( self.get_topic_hass_autoconfig_base())

    def get_topic_hass_autoconfig_base(self) -> str : 
        return self.topic_hass_autodisco_base

    def get_topic_hass_autoconfig(self, rel_topic:str) -> str :
        return MqttClient.clean_topic(f'{self.get_topic_hass_autoconfig_base()}/{rel_topic.rstrip("/")}')


    def _register_unique_topic(self, topic:str, is_subsciption:bool=False) -> None:
        self._check_unique_topic(topic, is_subsciption) 
        if is_subsciption:
            self.unique_topic_publish_list.append(topic)
        else:
            self.unique_topic_subscribe_list.append(topic)

    def _check_unique_topic(self, topic:str, is_subsciption:bool=False) -> None:
        if is_subsciption:
            if topic in self.unique_topic_publish_list:
                raise LookupError( f'Topic {topic} is already registered for publishing')
        else:
            if topic in self.unique_topic_subscribe_list:
                raise LookupError( f'Topic {topic} is already registered for subscription')


    def get_avail_message(self, is_avail:bool) -> str:
        msg = "True" if is_avail else "False"
        return msg


    #------------------------------------------------------------------------------------------------------------------
    # Callback methods
    #

    def on_connect_callback(self, mqc, userdata, flags, rc):
        if rc != 0:
            logger.error(f'MQTT Connection refused: {mqtt.connack_string(rc)}')
            return

        self.publish_daemon_availability(True)
        logger.info(f'MQTT Broker succesfully connected: {self.mqtt_host}: {self.mqtt_port}')

        mqc.subscribe(self.get_topic_reference_subsciption('+', '+'))
        logger.info(f'Subscribed to MQTT topic: {self.get_topic_reference_subsciption("+", "+")}')
        #XXX mqc.subscribe(self.topic_base + "/reset-autoremove")


    def on_disconnect_callback(self, mqc, userdata, rc):
        logger.info("MQTT Disconnected, RC:"+str(rc))

    def on_log_callback(self, mgc, userdata, level, buf):
        logger.log( level, f'MQTT log: {buf}')

    def on_message_callback(self, mqc, userdata, msg):
        self.modbus_writer.add_set_request(userdata, msg)
