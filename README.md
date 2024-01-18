# modbus2mqtt_2
Yet another Modbus master which publishes via MQTT

Written and (c) 2024 by Harald Roelle</br>
Provided under the terms of the GPL 3.0 license.

Contains some ideas/code/architecture taken from:
- modbus2mqtt - Modbus master with MQTT publishing
  - Written and (C) 2015 by Oliver Wagner <owagner@tellerulam.com>
  - Provided under the terms of the MIT license.
- spicierModbus2mqtt - Modbus master with MQTT publishing
  - Written and (C) 2018 by Max Brueggemann <mail@maxbrueggemann.de>
  - Provided under the terms of the MIT license.
  

## Overview
modbus2mqtt_2 is a Modbus master which continuously polls slaves and publishes values via MQTT.

It is intended as a building block in heterogeneous smart home environments where 
an MQTT message broker is used as the centralized message bus.

Special support is provided for Home Assistant (HASS).

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
- python3, version 3.11 or newer
- Eclipse Paho for Python - http://www.eclipse.org/paho/clients/python/
- pymodbus - https://github.com/riptideio/pymodbus
- pyyaml
- jsons

### Installation of requirements:
* Install python3 and python3-pip and python3-serial</br>
  On a Debian based system, something like `sudo apt install python3 python3-pip python3-serial` will likely get you there.
* run `pip3 install pymodbus`
* run `pip3 install paho-mqtt`
* run `pip3 install pyyaml`
* run `pip3 install jasons`

## Usage
* example for rtu and mqtt broker on localhost: `python3 modbus2mqtt.py --rtu /dev/ttyS0 --rtu-baud 38400 --rtu-parity none --mqtt-host localhost  --config testing.csv`
* example for tcp slave and mqtt broker
    on localhost: `python3 modbus2mqtt.py --tcp localhost --config testing.csv`
    remotely:     `python3 modbus2mqtt.py --tcp 192.168.1.7 --config example.csv --mqtt-host mqtt.eclipseprojects.io`

For docker support see below.
     
## Configuration file

## MQTT

Values are published as strings to topic:

`\<*prefix*\>/\<*device-name*\>/state/\<*reference-topic*\>"

A value will be published if:
  - It's formatted/calculated data has changed
  - Optionally, in a configurable regular interval, now matter if data has changed (option XXX)
The published MQTT messages do not have the retain flag set, but it can be turned on by the option XXX


A special topic "prefix/connected" is maintained. 
It states whether the module is currently running and connected to 
the broker (1) and to the Modbus interface (2).

We also maintain a "connected"-Topic for each poller (prefix/poller_topic/connected). This is useful when using Modbus RTU with multiple slave devices because a non-responsive device can be detected.

For diagnostic purposes (mainly for Modbus via serial) the topics prefix/poller_topic/state/diagnostics_errors_percent and prefix/poller_topic/state/diagnostics_errors_total are available. This feature can be enabled by passing the argument "--diagnostics-rate X" with x being the amount of seconds between each recalculation and publishing of the error rate in percent and the amount of errors within the time frame X. Set X to something like 600 to get diagnostic messages every 10 minutes.

Writing to Modbus coils and registers
------------------------------------------------

spiciermodbus2mqtt subscribes to:

"prefix/poller topic/set/reference topic"


If you want to write to a coil:

mosquitto_pub -h <mqtt broker> -t modbus/somePoller/set/someReference -m "True"

to a register:

mosquitto_pub -h <mqtt broker> -t modbus/somePoller/set/someReference -m "12346"


## References
