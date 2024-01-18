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
1. Install python3 and python3-pip and python3-serial<br>
  On a Debian based system, something like `sudo apt install python3 python3-pip python3-serial` will likely get you there.
1. run `pip3 install pymodbus`
1. run `pip3 install paho-mqtt`
1. run `pip3 install pyyaml`
1. run `pip3 install jasons`

## Usage
* example for rtu and mqtt broker on localhost: `python3 modbus2mqtt.py --rtu /dev/ttyS0 --rtu-baud 38400 --rtu-parity none --mqtt-host localhost  --config testing.csv`
* example for tcp slave and mqtt broker
    on localhost: `python3 modbus2mqtt.py --tcp localhost --config testing.csv`
    remotely:     `python3 modbus2mqtt.py --tcp 192.168.1.7 --config example.csv --mqtt-host mqtt.eclipseprojects.io`

## Docker
     
## Configuration file

## MQTT

### Value publishing
Values are published as strings to topic:

*`prefix`*/*`device-name`*/state/*`reference-topic`*

A value will be calculated from the raw value by:
  1. Applying a transformation according to the option `XXX`.
  2. Optionally, multiplying it by a scaling factor given by option `XXX`
  3. Optionally, formatting according to option `XXX`. This is a `printf`-like format string.<br>
     For example, to publish a value as a voltage value with one decimal place and the unit included: `XXX %.1fV`

A value will be published if:
  - It's formatted/calculated data has changed
  - Optionally, in a configurable regular interval, no matter if data has changed (option `XXX`)

The published MQTT messages do not have the retain flag set, but it can be turned on by the option `XXX`

### Availability / liveness publishing

To indicate if the daemon is alive, the following topic is maintained:<br>
`\<*prefix*\>/\<*mqtt-client-name*\>/connected/`<br>
`\<*mqtt-client-name*\>` is derived from the hostname or XXX

To indicate the liveness of certain device, the following topic is set accordingly:<br>
`\<*prefix*\>/\<*device-name*\>/value/connected/`<br>

### Diagnostics
For diagnostic purposes (mainly for Modbus via serial) the topics prefix/poller_topic/state/diagnostics_errors_percent and prefix/poller_topic/state/diagnostics_errors_total are available. This feature can be enabled by passing the argument "--diagnostics-rate X" with x being the amount of seconds between each recalculation and publishing of the error rate in percent and the amount of errors within the time frame X. Set X to something like 600 to get diagnostic messages every 10 minutes.

### Writing to Modbus coils and registers

For writeable references (option XXX) the daemon subscribes to 
`\<*prefix*\>/\<*device-name*\>/set/\<*reference-topic*\>`

On receiving a message from MQTT, the inferse transformation for XXX will be applied and the data is written to the Modbus device.

## References
