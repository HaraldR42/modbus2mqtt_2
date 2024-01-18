# modbus2mqtt_2
Yet another Modbus master which publishes via MQTT

Written and (c) 2024 by Harald Roelle
Provided under the terms of the GPL 3.0 license.

Contains some ideas/code/architecture taken from:
- modbus2mqtt - Modbus master with MQTT publishing
  - Written and (C) 2015 by Oliver Wagner <owagner@tellerulam.com>
  - Provided under the terms of the MIT license.
- spicierModbus2mqtt - Modbus master with MQTT publishing
  - Written and (C) 2018 by Max Brueggemann <mail@maxbrueggemann.de>
  - Provided under the terms of the MIT license.
  

## Overview
modbus2mqtt_2 is a Modbus master which continuously polls slaves and publishes
values via MQTT.

It is intended as a building block in heterogeneous smart home environments where 
an MQTT message broker is used as the centralized message bus.

Special support is provided for Home Assistant.

## Why _2 ?
Main improvements and changes over spicierModbus2mqtt:
- Almost complete rewrite
- Completely async main loop / polling.
- Improved modularization of code
- Changed config file format to yaml:
    - All daemon options can (and should) go into the yaml file
    - Command line options still provided for compatibility. Commandline overrules config file.
    - Introduced device specification. Hierarchy is now Device -> Poller -> Reference
    - Old CSV format still supported, but not all features available.
- Massively improved Home Assistant (HASS) integration
    - Minimal integration almost out of the box
    - Additional HASS properties can be set for each device and reference
    - Default option setting possible to reduce config file size
- Optional printf like MQTT output formatting for references (only via yaml)
- Optionally, references can have different modbus registers for writing than reading. Especially for supporting Wago devices.
- "Publish always" extended to cyclic forced publishing (or always)
- Modbus values published without retain flag. This changes the default behaviour from spicierModbus2mqtt, but can be switched on by option.
- Cyclic publishing all values (even unchanged ones) in a configurable interval possible (not necessarily on every modbus read)

## Installation
Requirements:

* python3.11
* Eclipse Paho for Python - http://www.eclipse.org/paho/clients/python/
* pymodbus - https://github.com/riptideio/pymodbus
* pyyaml
* jsons

### Installation of requirements:

* Install python3 and python3-pip and python3-serial (on a Debian based system something like sudo apt install python3 python3-pip python3-serial will likely get you there)
* run pip3 install pymodbus
* run pip3 install paho-mqtt

## Usage
* example for rtu and mqtt broker on localhost: `python3 modbus2mqtt.py --rtu /dev/ttyS0 --rtu-baud 38400 --rtu-parity none --mqtt-host localhost  --config testing.csv`
* example for tcp slave and mqtt broker
    on localhost: `python3 modbus2mqtt.py --tcp localhost --config testing.csv`
    remotely:     `python3 modbus2mqtt.py --tcp 192.168.1.7 --config example.csv --mqtt-host mqtt.eclipseprojects.io`

For docker support see below.
     
## Configuration file

modbus2mqtt_2 supports two basic variants of configuration:
1. Commandline + .csv file
This is the original way of spicierModbus2mqtt. It is still supported, but doesn't offer all features, especially on HASS integration. 
For details see https://github.com/mbs38/spicierModbus2mqtt#configuration-file.
Not recommended.
> Please note: Some configuration options changed from spicierModbus2mqtt. Also some of the defaults. Please review your commandline when using this variant
1. YAML configuration file
Setting all options by a YAML file. The only commandline option required is using `--config` to point to config file.

### YAML based configuration
The YAML config has two main parts:
1. Daemon:
Here go all options that config the MQTT broker connection and the Modbus interface.
It replaces all commandline options.
2. Devices:
This is where the definition of devices, pollers and references go.
It replaces the .csv file.

#### YAML `Daemon:` options
    Daemon:
      rtu: null
      tcp: null
      mqtt-host: localhost
      mqtt-port: null
      mqtt-user: null
      mqtt-pass: ''
      mqtt-use-tls: false
      mqtt-insecure: false
      mqtt-cacerts: null
      mqtt-tls-version: null
      mqtt-topic: modbus/
      publish-seconds: 300
      retain-values: false
      rtu-baud: 19200
      rtu-parity: even
      tcp-port: 502
      set-modbus-timeout: 1.0
      avoid-fc6: false
      diagnostics-rate: 0
      add-to-homeassistant: false
      hass-discovery-prefix: homeassistant
      verbosity: debug

#### YAML `Devices:` options
    Devices:
    - name: null
      slave-id: null

#### YAML `Pollers:` options
      Pollers:
      - start-reg: null
        len-regs: 1
        reg-type: coil
        poll-rate: 15.0

#### YAML `References:` options
        References:
        - topic: null
          start-reg: null
          write-reg: null
          readable: true
          writeable: false
          data-type: null
          scaling: null
          format-str: null
          hass_entity_type: null


### Home Assistant Options (HASS)
The following options are only required if one has enabled HASS integration.
For simplicity, just some snippets from the code are provided.
For more extensive information on the options, please see the HASS documentation of the MQTT integration and discovery (https://www.home-assistant.io/integrations/mqtt/#mqtt-discovery)

#### HASS Device Options
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

#### HASS Generic Entity Options (applies to specific ones)
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

#### HASS Specific Entity Options for Binary_Sensors
    # --- User settable options ---------------------------------------------------------------
    #                                       |     | Auto  | 
    #                                       | Req | deflt | Description
    #                                       +-----+-------+------------------------------------
    'last_reset_value_template':    None, # |     |       | Defines a template to extract the last_reset.
    'off_delay':                    None, # |     |       | For sensors that only send on state updates (like PIRs), this variable sets a delay in seconds after which the sensor’s state will be updated back to off.
    'payload_off':                  None, # |     |       | The string that represents the off state. It will be compared to the message in the state_topic (see value_template for details)
    'payload_on':                   None, # |     |       | The string that represents the on state. It will be compared to the message in the state_topic (see value_template for details)
    'value_template':               None, # |     |       | Defines a template that returns a string to be compared to payload_on/payload_off or an empty string, in which case the MQTT message will be removed. Remove this option when payload_on and payload_off are sufficient to match your payloads (i.e no pre-processing of original message is required).

#### HASS Specific Entity Options for Sensors
    # --- User settable options ---------------------------------------------------------------
    #                                       |     | Auto  | 
    #                                       | Req | deflt | Description
    #                                       +-----+-------+------------------------------------
    'suggested_display_precision':  None, # |     |       | The number of decimals which should be used in the sensor’s state after rounding.
    'state_class':                  None, # |     |       | The state_class of the sensor. (not supported by all entity types!)
    'unit_of_measurement':          None, # |     |       | Defines the units of measurement of the sensor, if any. The unit_of_measurement can be null.
    'value_template':               None, # |     |       | Defines a template to extract the value. If the template throws an error, the current state will be used instead.

#### HASS Specific Entity Options for Switches
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
