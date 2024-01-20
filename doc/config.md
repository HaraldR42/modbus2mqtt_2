# Configuration of modbus2mqtt_2

*modbus2mqtt_2* supports two basic variants of configuration:

[Command line + .csv file (legacy and limited)](#command-line--csv-file)<br>
[YAML configuration file (new, with all features)](#yaml-configuration-file)<br>

Also have a look at the example configurations provided in the [config directory](config)


## Command line + .csv file

This is the original way of *spicierModbus2mqtt*. It is still supported, but doesn't offer all features, especially on HASS integration.<br>
Not recommended any longer.<br>
> Please note: Some configuration options changed from *spicierModbus2mqtt*. Also some of the defaults. Please review your command line when using this variant

### Command line options
    -h, --help            show this help message and exit
    --config CONFIG       Configuration file. Required!
    --rtu RTU             pyserial URL (or port name) for RTU serial port
    --tcp TCP             Act as a Modbus TCP master, connecting to host TCP

  MQTT broker options:
    All options for connecting to an MQTT broker

    --mqtt-host MQTT_HOST
                          MQTT server address. Default: "localhost"
    --mqtt-port MQTT_PORT
                          Defaults to 8883 for TLS or 1883 for non-TLS
    --mqtt-clientid MQTT_CLIENTID
                          ID of our MQTT client. Default: "mb2mqtt-<hostname>"
    --mqtt-user MQTT_USER
                          Username for authentication (optional)
    --mqtt-pass MQTT_PASS
                          Password for authentication (optional)
    --mqtt-use-tls MQTT_USE_TLS
                          Use TLS. Default: "False"
    --mqtt-insecure MQTT_INSECURE
                          Use TLS without providing certificates. Default: "False"
    --mqtt-cacerts MQTT_CACERTS
                          Path to keychain
    --mqtt-tls-version {tlsv1.2,tlsv1.1,tlsv1}
                          TLS protocol version, can be one of tlsv1.2 tlsv1.1 or tlsv1.

  MQTT publish options:
    All options influencing the MQTT related behaviour

    --mqtt-topic MQTT_TOPIC
                          Topic prefix to be used for subscribing/publishing. Default: "modbus/"
    --mqtt-value-qos {0,1,2}
                          QoS value for publishing values. Default: "0"
    --publish-seconds PUBLISH_SECONDS
                          Publish values after n seconds (0=always), even if they did not change. Default: 300
    --retain-values RETAIN_VALUES
                          Set retain flag for published modbus values. Default: "False"

  Modbus connection options:
    All options influencing the Modbus connection related behaviour

    --rtu-baud RTU_BAUD   Baud rate for serial port. Default: "19200"
    --rtu-parity {even,odd,none}
                          Parity for serial port. Default: "even"
    --tcp-port TCP_PORT   Port for MODBUS TCP. Default: "502"

  Modbus running options:
    Modbus related options during running

    --set-modbus-timeout SET_MODBUS_TIMEOUT
                          Response time-out for Modbus devices. Default: "1.0"
    --avoid-fc6 AVOID_FC6
                          If set, use function code 16 (write multiple registers) even when just writing a single register. Default: "False"

  Misc options:

    --diagnostics-rate DIAGNOSTICS_RATE
                          Time in seconds after which for each device diagnostics are published via mqtt. Default: "0"
    --add-to-homeassistant ADD_TO_HOMEASSISTANT
                          Add devices to Home Assistant using Home Assistant's MQTT-Discovery. Default: "False"
    --verbosity {debug,info,warning,error,critical}
                          Verbosity level. Default: "info"


### .csv file
For details see https://github.com/mbs38/spicierModbus2mqtt#configuration-file.

## YAML configuration file
All options can be set by a YAML file. The only command line option required is using `--config` to point to config file.

Command line option can be used to override options from the yaml config.

### Basic YAML structure
The YAML config has two main parts:

1. `Daemon:`
Here go all options that config the MQTT broker connection and the Modbus interface.<br>
It replaces all command line options.

2. `Devices:`
This is where the definition of devices, pollers and references go.<br>
It replaces the .csv file.<br>

The overall YAML structure looks like this

    Daemon:
      daemon-option: value
      daemon-option: value
      daemon-option: value

    Devices:

      - name: device-1
        device-option: value
        device-option: value
        device-option: value
        Pollers:
          - start-reg: 0x0200 # First poller of first device
            poller-option: value
            poller-option: value
            poller-option: value
            References:
              - topic: topic1
                start-reg: 0x0200
                reference-option: value
              - topic: topic2
                start-reg: 0x0201
                reference-option: value
          - start-reg: 0x0400 # Second poller of first device
            References:
              - topic: topic1
                start-reg: 0x0400
              - topic: topic2
                start-reg: 0x0401

      - name: device-2
        Pollers:
          - start-reg: 0x0200 # First poller of second device
            References:
              - topic: topic
              - topic: topic2-2
          - start-reg: 0x0400 # Second poller of second device
            References:
              - topic: topic1
                start-reg: 0x0400
              - topic: topic2
                start-reg: 0x0401


### YAML `Daemon:` options
Below all daemon options and their default values. For a short description for the individual values, see the command line section above.

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


### YAML `Devices:` options
    Devices:
    - name: null
      slave-id: null

### YAML `Pollers:` options
      Pollers:
      - start-reg: null
        len-regs: 1
        reg-type: coil
        poll-rate: 15.0

### YAML `References:` options
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

### Setting default values
For `Pollers:` and `References:`, default options can be set in the hierarchy one level above by prepending `Default-` to any option. For example:

    Devices:
      - name: device-1
        device-option: value
        Default-poller-option: default-value-for-pollers-below
        Pollers:
          - start-reg: 0x0200 # First poller of first device
            poller-option: value
            Default-reference-option: default-value-for-references-below
            References:

See the [example config file for WAGO I/O](/config/wago-352-530-430.yaml). It illustrates quite well how one can write compact config files by using the default mechanism.

## Home Assistant Options (HASS)
The following options are only required if one has enabled HASS integration.
For simplicity, just some snippets from the code are provided.
For more extensive information on the options, please see the HASS documentation of the MQTT integration and discovery (https://www.home-assistant.io/integrations/mqtt/#mqtt-discovery)

See also the [example config file for Eastron power meter](/config/eastron-sdm72.yaml). There you can see how one could use the additional HASS options.

### HASS Device Options
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

### HASS Generic Entity Options (applies to specific ones)
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

### HASS Specific Entity Options for Binary_Sensors
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

### HASS Specific Entity Options for Switches
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
