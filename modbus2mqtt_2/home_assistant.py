import json
import re
import jsons

from .mqtt_client import MqttClient
from .modbus_objects import Device, Reference
from .globals import logger, __myname__


###################################################################################################################
#
# Decorator definition for static initializers
#

def staticinit(cls):
    if getattr(cls, "__staticinit__", None):
        cls.__staticinit__()
    return cls


###################################################################################################################
#
# Interface class for generating autodiscovery information
#

class HassConnector:
    @classmethod
    def publish_hass_autodiscovery(cls, mqttc:MqttClient) -> None :
        mqttc.register_hass_topics()
        for dev in Device.all_devices.values() :
            ha_dev = HassDevice( dev)
            for ref in dev.references.values() :
                try:
                    ha_entity = HassEntity.new_entity_for_reference(ref, ha_dev)
                    autodisco_topic = ha_entity.get_autodiscovery_rel_topic()
                    json_str = ha_entity.get_autodiscovery_value()
                    mqttc.publish_hass_autodiscovery_entity(autodisco_topic, json_str)
                except Exception as e:
                    logger.warning( f'Home Assistant: Error generating autodiscovery for  "{ref.poller.device.name}/{ref.topic}": {e}')


###################################################################################################################
#
# Public classes for HASS objects
#

class HassDevice :

    # remember to mark values not for serialization to json as private
    _config_options = {         
        # --- User settable options ---------------------------------------------------------------
        #                                       |     | Auto  | 
        #                                       | Req | deflt | Description
        #                                       +-----+-------+------------------------------------
        'configuration_url':    None, #         |     |       | A link to the webpage that can manage the configuration of this device. Can be either an http://, https:// or an internal homeassistant:// URL.
        'connections':          None, #         |     |       | A list of connections of the device to the outside world as a list of tuples [connection_type, connection_identifier].
        'hw_version':           None, #         |     |       | The hardware version of the device.
        'manufacturer':         None, #         |     |       | The manufacturer of the device.
        'model':                None, #         |     |       | The model of the device.
        'name':                 None, #         |     |   X   | The name of the device.
        'suggested_area':       None, #         |     |       | Suggest an area if the device isn’t in one yet.
        'sw_version':           None, #         |     |       | The firmware version of the device.
        'via_device':           None, #         |     |       | Identifier of a device that routes messages between this device and Home Assistant.

        # --- NOT settable options ----------------------------------------------------------------
        #                                       |     | Auto  | 
        #                                       | Req | set   | Description
        #                                       +-----+-------+------------------------------------
        # identifiers                           |     |   X   | A list of IDs that uniquely identify the device.
    }

    @classmethod
    def get_config_options(cls) -> dict() :
        return HassDevice._config_options

    def __init__(self, dev:Device) -> None:
        # remember to mark values not for serialization to json as private
        self.name:str = dev.name # The name of the device.
        self.identifiers:list = list() # A list of IDs that uniquely identify the device. For example a serial number.
        self.identifiers.append(HassEntity._ha_id_from_str(f'{__myname__}-{dev.name}'))
        for attr, value in dev.ha_properties.items():
            if value != None:
                setattr( self, attr, value)


class HassEntity :

    # remember to mark values not for serialization to json as private
    _all_entity_types = dict()
    _entity_type = None
    _config_options = {
        # --- User settable options ---------------------------------------------------------------
        #                                       |     | Auto  | 
        #                                       | Req | deflt | Description
        #                                       +-----+-------+------------------------------------
        'device_class':                 None, # |     |       | Sets the class of the device, changing the device state and icon that is displayed on the frontend. The device_class can be null.
        'enabled_by_default':           None, # |     |       | Flag which defines if the entity should be enabled when first added.
        'encoding':                     None, # |     |       | The encoding of the payloads received. Set to "" to disable decoding of incoming payload.
        'entity_category':              None, # |     |       | The category of the entity. When set, the entity category must be diagnostic for sensors.
        'expire_after':                 None, # |     |       | If set, it defines the number of seconds after the sensor’s state expires, if it’s not updated. After expiry, the sensor’s state becomes unavailable. Default the sensors state never expires.
        'force_update':                 None, # |     |       | Sends update events (which results in update of state object’s last_changed) even if the sensor’s state hasn’t changed. Useful if you want to have meaningful value graphs in history or want to create an automation that triggers on every incoming state message (not only when the sensor’s new state is different to the current one).
        'icon':                         None, # |     |       | Icon for the entity.
        'json_attributes_template':     None, # |     |       | Defines a template to extract the JSON dictionary from messages received on the json_attributes_topic. Usage example can be found in MQTT sensor documentation.
        'json_attributes_topic':        None, # |     |       | The MQTT topic subscribed to receive a JSON dictionary payload and then set as sensor attributes. Usage example can be found in MQTT sensor documentation.
        'name':                         None, # |     |   X   | The name of the entity. Can be set to null if only the device name is relevant.
        'object_id':                    None, # |     |       | Used instead of name for automatic generation of entity_id
        'qos':                          None, # |     |       | The maximum QoS level to be used when receiving and publishing messages.
        'unique_id':                    None, # |     |   X   | An ID that uniquely identifies this sensor. If two sensors have the same unique ID, Home Assistant will raise an exception.

        # --- NOT settable options ----------------------------------------------------------------
        #                                       |     | Auto  | 
        #                                       | Req | set   | Description
        #                                       +-----+-------+------------------------------------
        # availability                          |     |   X   | A list of MQTT topics subscribed to receive availability (online/offline) updates
        # availability_mode                     |     |   X   | This controls the conditions needed to set the entity to available. Valid entries are all, any, and latest.
        # availability_template                 |     |       | (handled by 'availability')
        # availability_topic                    |     |       | (handled by 'availability')
        # device                                |     |   X   | Information about the device this sensor is a part of to tie it into the device registry. Only works when unique_id is set.
        # payload_available                     |     |       | (handled by 'availability')
        # payload_not_available                 |     |       | (handled by 'availability')
        # state_topic                           |  X  |   X   | The MQTT topic subscribed to receive sensor values.
    }


    #==================================================================================================================
    #
    # Class methods
    #

    @classmethod
    def __staticinit__(cls) -> None:
        pass

    @classmethod
    def _register_entity_type(cls) -> None:
        HassEntity._all_entity_types[cls._entity_type] = cls

    @classmethod
    def _get_config_opts_recursive(cls):
        if cls.__base__ == object:
            return cls._config_options
        else:
            return cls._config_options | cls.__base__._get_config_opts_recursive()

    @classmethod
    def _ha_id_from_str(cls, val:str) -> str :
        out = val.strip()
        out = out.strip( '/')
        out = re.sub( r"[^a-zA-Z0-9_-]", "_", out)
        return out

    @classmethod
    def get_entity_type(cls) -> str:
        return cls._entity_type

    @classmethod
    def get_valid_config_opts(cls, entity_type) -> dict:
        if entity_type not in HassEntity._all_entity_types:
            raise LookupError( f'Entity type {entity_type} unknown')
        return HassEntity._all_entity_types[entity_type]._get_config_opts_recursive()

    @classmethod
    def get_all_config_opts(cls) -> dict:
        all = dict()
        for type_class in HassEntity._all_entity_types.values():
            all = all | type_class._config_options
        return all
    
    @classmethod
    def new_entity_for_reference(cls, ref:Reference, ha_dev:HassDevice) -> "HassEntity":
        if not ref.hass_entity_type :
            raise ValueError( f'Home Assistant: Ignoring "{ref.poller.device.name}/{ref.topic}" for autodiscovery: "hass_entity_type" not set.')
        if ref.hass_entity_type not in HassEntity._all_entity_types:
            raise ValueError( f'Home Assistant: Ignoring "{ref.poller.device.name}/{ref.topic}" for autodiscovery: Entity type "{ref.hass_entity_type}" unknown.')
        return HassEntity._all_entity_types[ref.hass_entity_type](ref, ha_dev) # return instance of the appropriate subclass


    #==================================================================================================================
    #
    # Instance methods
    #

    def __init__(self, ref:Reference, ha_dev:HassDevice) -> None:
        # remember to mark values not for serialization to json as private
        self._ref=ref
        self._entity_type = ref.hass_entity_type

        self.availability:list = list()
        self.availability.append(_HassAvailability(ref.mqttc.get_topic_daemon_avail(),ref.mqttc))
        self.availability.append(_HassAvailability(ref.mqttc.get_topic_device_availability(ref.poller.device.name),ref.mqttc))
        self.availability_mode = 'all'
        self.device:HassDevice = ha_dev

        self.name = ref.topic[:1].upper() + ref.topic[1:]
        self.unique_id:str = HassEntity._ha_id_from_str(f'{__myname__}-{ref.poller.device.name}-{ref.topic}')
        if (ref.is_readable) :
            self.state_topic:str = ref.mqttc.get_topic_reference_value(ref.poller.device.name, ref.topic) # The MQTT topic subscribed to receive sensor’s state.

        for attr, value in ref.ha_properties.items():
            if value != None:
                setattr( self, attr, value)

    def get_autodiscovery_rel_topic(self) -> str:
        # <discovery_prefix>/<component>/[<node_id>/]<object_id>/config
        node_id = HassEntity._ha_id_from_str(self._ref.poller.device.name)
        obj_id = HassEntity._ha_id_from_str(self._ref.topic)
        return f'{self._entity_type}/{node_id}/{obj_id}/config'

    def get_autodiscovery_value(self) -> str:
        dump = jsons.dump(self, strip_nulls=False, strip_privates=True)
        #dump = jsons.dump(self, strip_nulls=True, strip_privates=True)
        return json.JSONEncoder( skipkeys=False, ensure_ascii=True, check_circular=True, allow_nan=True, sort_keys=False, indent=2, separators=None, default=None).encode(dump)


###################################################################################################################
#
# Internal classes of HASS, but defining publicly available yaml configuration options
#

@staticinit
class _HassBinarySensor(HassEntity):

    # remember to mark values not for serialization to json as private
    _entity_type = "binary_sensor"
    _config_options = {
        # --- User settable options ---------------------------------------------------------------
        #                                       |     | Auto  | 
        #                                       | Req | deflt | Description
        #                                       +-----+-------+------------------------------------
        'last_reset_value_template':    None, # |     |       | Defines a template to extract the last_reset.
        'off_delay':                    None, # |     |       | For sensors that only send on state updates (like PIRs), this variable sets a delay in seconds after which the sensor’s state will be updated back to off.
        'payload_off':                  None, # |     |       | The string that represents the off state. It will be compared to the message in the state_topic (see value_template for details)
        'payload_on':                   None, # |     |       | The string that represents the on state. It will be compared to the message in the state_topic (see value_template for details)
        'value_template':               None, # |     |       | Defines a template that returns a string to be compared to payload_on/payload_off or an empty string, in which case the MQTT message will be removed. Remove this option when payload_on and payload_off are sufficient to match your payloads (i.e no pre-processing of original message is required).
    }

    @classmethod
    def __staticinit__(cls):
        cls._register_entity_type()


@staticinit
class _HassSensor(HassEntity):

    # remember to mark values not for serialization to json as private
    _entity_type = "sensor"
    _config_options = {
        # --- User settable options ---------------------------------------------------------------
        #                                       |     | Auto  | 
        #                                       | Req | deflt | Description
        #                                       +-----+-------+------------------------------------
        'suggested_display_precision':  None, # |     |       | The number of decimals which should be used in the sensor’s state after rounding.
        'state_class':                  None, # |     |       | The state_class of the sensor. (not supported by all entity types!)
        'unit_of_measurement':          None, # |     |       | Defines the units of measurement of the sensor, if any. The unit_of_measurement can be null.
        'value_template':               None, # |     |       | Defines a template to extract the value. If the template throws an error, the current state will be used instead.
    }

    @classmethod
    def __staticinit__(cls):
        cls._register_entity_type()


@staticinit
class _HassSwitch(HassEntity):

    # remember to mark values not for serialization to json as private
    _entity_type = "switch"
    _config_options = {
        # --- User settable options ---------------------------------------------------------------
        #                                       |     | Auto  | 
        #                                       | Req | deflt | Description
        #                                       +-----+-------+------------------------------------
        'optimistic':           None, #         |     |       |  Flag that defines if switch works in optimistic mode. Default: true if no state_topic defined, else false.
        'payload_off':          None, #         |     |       | (optional, default: OFF) The payload that represents off state. If specified, will be used for both comparing to the value in the state_topic (see value_template and state_off for details) and sending as off command to the command_topic.
        'payload_on':           None, #         |     |       | (optional, default: ON) The payload that represents on state. If specified, will be used for both comparing to the value in the state_topic (see value_template and state_on for details) and sending as on command to the command_topic.
        'retain':               None, #         |     |       | (optional, default: false) If the published message should have the retain flag on or not.
        'state_off':            None, #         |     |       | (optional) The payload that represents the off state. Used when value that represents off state in the state_topic is different from value that should be sent to the command_topic to turn the device off. Default: payload_off if defined, else OFF
        'state_on':             None, #         |     |       | (optional) The payload that represents the on state. Used when value that represents on state in the state_topic is different from value that should be sent to the command_topic to turn the device on. Default: payload_on if defined, else ON
        'value_template':       None, #         |     |       | (optional) Defines a template to extract device’s state from the state_topic. To determine the switches’s state result of this template will be compared to state_on and state_off.

        # --- NOT settable options ----------------------------------------------------------------
        #                                       |     | Auto  | 
        #                                       | Req | set   | Description
        #                                       +-----+-------+------------------------------------
        # command_topic                         |  X  |   X   | The MQTT topic to publish commands to change the switch state.
    }

    @classmethod
    def __staticinit__(cls):
        cls._register_entity_type()

    def __init__(self, ref:Reference, ha_dev:HassDevice) -> None:
        # remember to mark values not for serialization to json as private
        super().__init__(ref, ha_dev)
        if not ref.is_writeable :
            raise ValueError(f'Reference "{ref.poller.device.name}/{ref.topic}" must be writeable to act as a switch')
        self.command_topic:str = ref.mqttc.get_topic_reference_subsciption(ref.poller.device.name, ref.topic)


class _HassAvailability:
        # --- NOT settable options ----------------------------------------------------------------
        #                                       |     | Auto  | 
        #                                       | Req | set   | Description
        #                                       +-----+-------+------------------------------------
        # payload_available                     |     |   X   | The payload that represents the available state.
        # payload_not_available                 |     |   X   | The payload that represents the unavailable state.
        # topic                                 |  X  |   X   | An MQTT topic subscribed to receive availability (online/offline) updates.
        # value_template                        |     |       | value_template template.

    def __init__(self, topic:str, mqttc:MqttClient) -> None:
        # remember to mark values not for serialization to json as private
        self.topic:str = topic 
        self.payload_available:str = mqttc.get_avail_message(True)
        self.payload_not_available:str = mqttc.get_avail_message(False)
