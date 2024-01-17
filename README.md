# modbus2mqtt_2
Yet another Modbus master which publishes via MQTT

modbus2mqtt_2
==================

Written and (c) 2024 by Harald Roelle
Provided under the terms of the GPL 3.0 license.

Contains some ideas/code/architecture taken from:
- modbus2mqtt - Modbus master with MQTT publishing
  - Written and (C) 2015 by Oliver Wagner <owagner@tellerulam.com>
  - Provided under the terms of the MIT license.
- spicierModbus2mqtt - Modbus master with MQTT publishing
  - Written and (C) 2018 by Max Brueggemann <mail@maxbrueggemann.de>
  - Provided under the terms of the MIT license.
  

Overview
--------
modbus2mqtt_2 is a Modbus master which continuously polls slaves and publishes
values via MQTT.

It is intended as a building block in heterogeneous smart home environments where 
an MQTT message broker is used as the centralized message bus.

Special support is provided for Home Assistant.

Why _2 ?
--------
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

Installation
------------
Requirements:

* python3.11
* Eclipse Paho for Python - http://www.eclipse.org/paho/clients/python/
* pymodbus - https://github.com/riptideio/pymodbus
* pyyaml
* jsons

Installation of requirements:

* Install python3 and python3-pip and python3-serial (on a Debian based system something like sudo apt install python3 python3-pip python3-serial will likely get you there)
* run pip3 install pymodbus
* run pip3 install paho-mqtt

Usage
-----
* example for rtu and mqtt broker on localhost: `python3 modbus2mqtt.py --rtu /dev/ttyS0 --rtu-baud 38400 --rtu-parity none --mqtt-host localhost  --config testing.csv`
* example for tcp slave and mqtt broker
    on localhost: `python3 modbus2mqtt.py --tcp localhost --config testing.csv`
    remotely:     `python3 modbus2mqtt.py --tcp 192.168.1.7 --config example.csv --mqtt-host mqtt.eclipseprojects.io`

For docker support see below.
     
Configuration file
-------------------

TO BE CONTINUED
