# modbus2mqtt_2
Yet another Modbus master which publishes via MQTT (and vice versa).<br>
As there are many others, its name is pronounced *modbus2mqtt* **too** ;-)

Written and (c) 2024 by Harald Roelle</br>
Provided under the terms of the GPL 3.0 license.

Contains ideas/code/architecture taken from:
- *spicierModbus2mqtt* - Modbus master with MQTT publishing
  - Written and (C) 2018 by Max Brueggemann <mail@maxbrueggemann.de>
  - Provided under the terms of the MIT license.  

## Overview
*modbus2mqtt_2* is a Modbus master which continuously polls slaves and publishes values via MQTT.

It is intended as a building block in heterogeneous smart home environments where 
an MQTT message broker is used as the centralized message bus.<br>
**Special support is provided for Home Assistant (HASS).**

## Why _2 ?
Main improvements and changes over *spicierModbus2mqtt*:
- Almost complete rewrite
- Completely async main loop / polling. Very fast, at least with TCP.
- Improved modularization of code
- Changed config file format to yaml:
    - All daemon options can (and should) go into the yaml file
    - Command line options still provided for compatibility. Command line overrules config file.
    - Introduced device specification. Hierarchy is now Device -> Poller -> Reference
    - Old CSV format still supported, but not all features are available.
- Massively improved Home Assistant (HASS) integration
    - Minimal integration almost out of the box, just one option needs to be provided
    - Additional HASS properties can be set for each device and reference in the config file
    - Default option setting possible to reduce config file size
- Optional printf like MQTT output formatting for references (only via yaml)
- Optionally, references can have different modbus registers for writing than reading. Especially for supporting Wago devices.
- Modbus values published without retain flag. This changes the default behavior from *spicierModbus2mqtt*, but can be switched on by option.
- Cyclic publishing all values (even unchanged ones, "Publish always") now possible in a configurable interval (not necessarily on every modbus read)
- Extended diagnostics
- Extended data types: All data types work for read and write, list data taype for all basic data types

## Installation
Requirements:
- python3, version 3.11 or newer
- [Eclipse Paho for Python](http://www.eclipse.org/paho/clients/python/)
- [pymodbus](https://github.com/riptideio/pymodbus)
- [pyyaml](https://pyyaml.org/)
- [jsons](https://github.com/ramonhagenaars/jsons)

### Installation of requirements:
1. Install python3 and python3-pip and python3-serial<br>
  On a Debian based system, something like `sudo apt install python3 python3-pip python3-serial` will likely get you there.
1. run `pip3 install pymodbus`
1. run `pip3 install paho-mqtt`
1. run `pip3 install pyyaml`
1. run `pip3 install jsons`

## Configuration and usage

*modbus2mqtt_2* supports two basic variants of configuration and launching:

1. Command line + .csv file (legacy and limited)<br>
   `python3 modbus2mqtt.py --config path-to-file.csv ... (lots of command line options)`
2. YAML configuration file (new, with all features)<br>
   `python3 modbus2mqtt.py --config path-to-file.yaml`

Please see [Configuration Documentation](doc/config.md) for details.<br>
Also have a look at the example configurations provided in the [config directory](config)

## Docker
*modbus2mqtt_2* can be run as a docker container, using the included Dockerfile. It allows all usual configuration options, with the expectation that it's configuration is at `/app/conf/modbus2mqtt_2.yaml`. For example:

To build the image:

`docker build -t modbus2mqtt_2 .`

To run the image:

`docker run -v $(pwd)/config/wago-352-530-430.yaml:/app/conf/modbus2mqtt_2.yaml --name modbus2mqtt_2 --hostname docker-m2m_2 -e TZ=Europe/Berlin modbus2mqtt_2`


## Tested Modbus devices and feedback
- Power meter **Eastron** **SDM72D-M-2-MID** via **Waveshare** **RS485 TO ETH (B)**
- Decentralized I/O from **WAGO**:
  - Ethernet head unit model **750-352**
  - Digital output model **750-530**
  - Digital input model **750-430**
- **Waveshare** **8-ch Ethernet Relay Module, Modbus TCP**

> All testing has been done only via Modbus TCP. Please provide **any** experience with other devices via the Github Issue Tracker, especially when connected with Modbus RTU!

## MQTT

### Value publishing
Values are published as strings to topic:

*`mqtt-topic`* **/** *`device-name`* **/ state /** *`reference-topic`*<br>
- The prefix of all MQTT topics can be specified by option `mqtt-topic`
- The *`device-name`* is specified by option `name` in the "Devices" section
- the *`reference-topic`* is specified by option `topic` in the "References" section of a device

A value will be calculated from the raw Modbus value by:
  1. Applying a transformation according to the option `data-type`.
  2. Optionally, multiplying it by a scaling factor given by option `scaling`
  3. Optionally, formatting according to option `format-str`. This is a *printf*-like format string.<br>
     For example, to publish a *float32* as a voltage value with one decimal place and the unit included: `format-str: "%.1fV"`

A value will be published if:
  - It's formatted/calculated data has changed (This changed from *spicierModbus2mqtt*)
  - Optionally, in a configurable regular interval, no matter if data has changed (option `publish-seconds`)

The published value messages do not have the MQTT retain flag set, but it can be turned on by the option `retain-values` (different to *spicierModbus2mqtt*).

### Availability / liveness publishing

To indicate if *modbus2mqtt_2* is alive, the following topic is maintained:<br>
*`mqtt-topic`* **/** *`mqtt-client-name`* **/ connected**<br>
*`mqtt-client-name`* is derived from the hostname or set by `mqtt-clientid`. Publishing is done as MQTT last-will-and-testament (LWT). Therefore, the status shall be correct even if *modbus2mqtt_2* dies unexpectedly.

To indicate the liveness of certain device, the following topic is set accordingly:<br>
*`mqtt-topic`* **/** *`device-name`* **/ connected**<br>
As this value is handled by *modbus2mqtt_2* alone, this value might be wrong when *modbus2mqtt_2* died unexpectedly.

### Diagnostics
For diagnostic purposes (mainly for Modbus via serial) the topic path <br>
*`mqtt-topic`* **/** *`device-name`* **/** **diagnostics / ...**<br>
is available. This feature can be enabled by passing the option `diagnostics-rate` with the number of seconds between each recalculation and publishing the diagnostic infos.

### Writing to Modbus coils and registers

For writeable references (option `writeable`) *modbus2mqtt_2* subscribes to <br>
*`mqtt-topic`* **/** *`device-name`* **/ set /** *`reference-topic`* <br>
On receiving a message from MQTT, the inverse transformation for `data-type` will be applied and the data is written to the Modbus device.

### Data types
For rendering the raw Modbus data, the following `data-type` values are supported
- `bool`
- `int16`
- `uint16`
- `int32LE`
- `int32BE`
- `uint32LE`
- `uint32BE`
- `float32LE`
- `float32BE`
- `stringLEx` with `x` being an even number of characters
- `stringBEx` with `x` being an even number of characters
- `list-dType-x` Generic list type: `dType` is one of the above data-types, x is the number of elements in the list. Example: `list-float32LE-5`

## References
This work is the result of personally not being satisfied with existing solutions (and me being in the mood to get my hands dirty :-)<br>
Nevertheless there are at some other projects that might suit your needs better (in no particular order, list is incomplete for sure):
- https://github.com/mbs38/spicierModbus2mqtt
- https://github.com/gavinying/modpoll
- https://github.com/BlackZork/mqmgateway
- https://github.com/owagner/modbus2mqtt
- https://github.com/Instathings/modbus2mqtt
- https://github.com/mazocode/modbus2mqtt
