#!/usr/bin/env python
#
# modbus2mqtt_2 - Yeat another Modbus TCP/RTU to MQTT bridge (and vice versa)
# https://github.com/HaraldR42/modbus2mqtt_2
#
# Written in 2024 by Harald Roelle
#
# Provided under the terms of the GPL 3.0 License
#
# Contains a bunch of code/architecture taken from:
# modbus2mqtt - Modbus master with MQTT publishing
#   Written and (C) 2015 by Oliver Wagner <owagner@tellerulam.com>
#   Provided under the terms of the MIT license.
# spicierModbus2mqtt - Modbus master with MQTT publishing
#   Written and (C) 2018 by Max Brueggemann <mail@maxbrueggemann.de>
#   Provided under the terms of the MIT license.
#
# Main improvements over spicierModbus2mqtt:
#   - Almost complete rewrite, polling architecture remains unchanged
#   - Improved modularization of code
#   - Changed config file format, unfortunately not compatible with spicierModbus2mqtt but quiete similar
#     - No format description in the first line required
#     - Introduced device specification. Hierarchy is now Device -> Poller -> Reference
#     - Optional printf like output formatting for references
#   - Massively improved Home Assistant integration
#     - Minimal integration out of the box
#     - Additional home assistant properties can be set for each reference
#   - More flexibility in mqtt topic specificaton
#   - "Publish always" extended to cyclic forced publishing (or always)
#   - Modbus values published without retain flag. Can be switched on by option.
#
# Requires:
# - Eclipse Paho for Python - http://www.eclipse.org/paho/clients/python/
# - pymodbus - https://github.com/riptideio/pymodbus
# - jsons
#
# To be tested:
# - Serial modbus
# - Setting coils
# - Everything about holding_register
#
# Features to implement
# - List data types
# - MQTT topic path
# - reenable logic
# - check python version
# - Use variable for daemon name, argparse setup


import argparse
import time
import sys
import signal
import asyncio

import modbus2mqtt_2.globals as globs
import modbus2mqtt_2.config_reader as config_reader

from .config_reader import ConfigNewCsv, ConfigYaml
from .globals import logger, deamon_opts
from .modbus_objects import ModbusMaster, Device, Poller, Reference
from .mqtt_client import MqttClient
from .home_assistant import HassConnector


class MainControl:
    run_loop = False

    def prepare_loop_start():
        MainControl.run_loop = True
        signal.signal(signal.SIGINT, MainControl.signal_handler)

    def stop_loop():
        MainControl.run_loop = False

    def signal_handler(signal, frame):
        logger.info('Exiting ' + sys.argv[0])
        MainControl.stop_loop()


def main():
    parser = argparse.ArgumentParser( description='Bridge between ModBus and MQTT')

    parser.add_argument('--config', required=True, type=argparse.FileType('r'), help='Configuration file. Required!')

    connTypeGroup = parser.add_mutually_exclusive_group(required=False)
    connTypeGroup.add_argument('--rtu', help='pyserial URL (or port name) for RTU serial port')
    connTypeGroup.add_argument('--tcp', help='Act as a Modbus TCP master, connecting to host TCP')

    mqttBrokerGroup = parser.add_argument_group( 'MQTT broker options', 'All options for connecting to an MQTT broker')
    mqttBrokerGroup.add_argument('--mqtt-host', help=f'MQTT server address. Default: "{deamon_opts["mqtt-host"]}"')
    mqttBrokerGroup.add_argument('--mqtt-port', type=int, help='Defaults to 8883 for TLS or 1883 for non-TLS')
    mqttBrokerGroup.add_argument('--mqtt-user', help='Username for authentication (optional)')
    mqttBrokerGroup.add_argument('--mqtt-pass', help='Password for authentication (optional)')
    mqttBrokerGroup.add_argument('--mqtt-use-tls', type=bool, help=f'Use TLS. Default: "{deamon_opts["mqtt-use-tls"]}"')
    mqttBrokerGroup.add_argument('--mqtt-insecure', type=bool, help=f'Use TLS without providing certificates. Default: "{deamon_opts["mqtt-insecure"]}"')
    mqttBrokerGroup.add_argument('--mqtt-cacerts', help="Path to keychain")
    mqttBrokerGroup.add_argument('--mqtt-tls-version', choices=['tlsv1.2', 'tlsv1.1', 'tlsv1'], help=f'TLS protocol version, can be one of tlsv1.2 tlsv1.1 or tlsv1.')

    mqttPubGroup = parser.add_argument_group( 'MQTT publish options', 'All options influencing the MQTT related behaviour')
    mqttPubGroup.add_argument('--mqtt-topic', help=f'Topic prefix to be used for subscribing/publishing. Default: "{deamon_opts["mqtt-topic"]}"')
    mqttPubGroup.add_argument('--publish-seconds', type=int, help=f'Publish values after n seconds (0=always), even if they did not change. Default: {deamon_opts["publish-seconds"]}')
    mqttPubGroup.add_argument('--retain-values', type=bool, help=f'Set retain flag for published modbus values. Default: "{deamon_opts["retain-values"]}"')

    mbConnGroup = parser.add_argument_group( 'Modbus connection options', 'All options influencing the Modbus connection related behaviour')
    mbConnGroup.add_argument('--rtu-baud', type=int, help=f'Baud rate for serial port. Default: "{deamon_opts["rtu-baud"]}"')
    mbConnGroup.add_argument('--rtu-parity', choices=[ 'even', 'odd', 'none'], help=f'Parity for serial port. Default: "{deamon_opts["rtu-parity"]}"')
    mbConnGroup.add_argument('--tcp-port', type=int, help=f'Port for MODBUS TCP. Default: "{deamon_opts["tcp-port"]}"')

    mbWorkGroup = parser.add_argument_group( 'Modbus running options', 'Modbus related options during running')
    mbWorkGroup.add_argument('--set-modbus-timeout', type=float, help=f'Response time-out for Modbus devices. Default: "{deamon_opts["set-modbus-timeout"]}"')
    #mbWorkGroup.add_argument('--autoremove', action='store_true', help='Automatically remove poller if modbus communication has failed three times. Removed pollers can be reactivated by sending "True" or "1" to topic modbus/reset-autoremove')
    mbWorkGroup.add_argument('--set-loop-break', type=float, help=f'Set pause in main polling loop in sec. Default: "{deamon_opts["set-loop-break"]}"')
    mbWorkGroup.add_argument('--avoid-fc6', type=bool, help=f'If set, use function code 16 (write multiple registers) even when just writing a single register. Default: "{deamon_opts["avoid-fc6"]}"')

    miscGroup = parser.add_argument_group('Misc options', '')
    miscGroup.add_argument('--diagnostics-rate', type=int, help=f'Time in seconds after which for each device diagnostics are published via mqtt. Default: "{deamon_opts["diagnostics-rate"]}"')
    miscGroup.add_argument('--add-to-homeassistant', type=bool, help=f'Add devices to Home Assistant using Home Assistant\'s MQTT-Discovery. Default: "{deamon_opts["add-to-homeassistant"]}"')
    miscGroup.add_argument('--verbosity', choices=['debug', 'info', 'warning', 'error', 'critical'], help=f'Verbosity level. Default: "{deamon_opts["verbosity"]}"')

    args = parser.parse_args()

    # First parse daemon config from yaml
    if not args.config.name.endswith('.csv'):
        ConfigYaml.read_daemon_config(args.config)
    if config_reader.config_error_count > 0:
        logger.critical("Configuration error. Exiting.")
        sys.exit(1)

    # As commandline args take precedence, overwrite values with ones from commandline
    args_dict = vars(args)
    for key in args_dict:
        opts_key = key.replace('_','-')
        if opts_key not in deamon_opts:
            logger.error( f'Unknown commandline option "{opts_key}"')
            sys.exit(1)
        if args_dict[key] != None:
            deamon_opts[opts_key] = args_dict[key]

    logger.setLevel(deamon_opts['verbosity'].upper())

    if deamon_opts['mqtt-port'] is None:
        deamon_opts['mqtt-port'] = 8883 if deamon_opts['mqtt-use-tls'] else 1883

    logger.info( f'Starting spiciermodbus2mqtt V{globs.__version__}')

    # Setup MQTT Broker
    globs.mqtt_client = MqttClient(
                        mqtt_host=deamon_opts['mqtt-host'], 
                        mqtt_port=deamon_opts['mqtt-port'], 
                        mqtt_user=deamon_opts['mqtt-user'], 
                        mqtt_pass=deamon_opts['mqtt-pass'],
                        mqtt_cacerts=deamon_opts['mqtt-cacerts'], 
                        mqtt_insecure=deamon_opts['mqtt-insecure'], 
                        mqtt_tls_version=deamon_opts['mqtt-tls-version'], 
                        topic_base=deamon_opts['mqtt-topic'],
                        topic_hass_autodisco_base=deamon_opts['hass-discovery-prefix'],
                        retain_values=deamon_opts['retain-values']
                        )

    if deamon_opts['rtu']:
        modbus_master = ModbusMaster.new_modbus_rtu_master(deamon_opts['rtu'], deamon_opts['rtu-parity'], deamon_opts['rtu-baud'], deamon_opts['set-modbus-timeout'])
    elif deamon_opts['tcp']:
        modbus_master = ModbusMaster.new_modbus_tcp_master(deamon_opts['tcp'], deamon_opts['tcp-port'])
    else:
        logger.critical(f'No modbus master defined')
        sys.exit(1)

    if args.config.name.endswith('.csv'):
        ConfigNewCsv.read_devices(args.config, globs.mqtt_client, modbus_master)
    else:
        ConfigYaml.read_devices(args.config, globs.mqtt_client, modbus_master)
    if config_reader.config_error_count > 0:
        logger.critical("Configuration error. Exiting.")
        sys.exit(1)

    if len(Poller.all_poller) == 0:
        logger.critical("No pollers. Exiting.")
        sys.exit(1)

    logger.info(f'Config file {args.config.name} successfully read.')

    asyncio.run(async_main(modbus_master), debug=False)


async def async_main(modbus_master:ModbusMaster):
    logger.debug("Starting main loop.")
    MainControl.prepare_loop_start()

    # Loop until initial connection to mqtt server is made. Reconnect is handled my mqtt client internally.
    mqtt_connected = False
    while MainControl.run_loop and not mqtt_connected:
        mqtt_connected = globs.mqtt_client.make_initial_connection()
        if not mqtt_connected:
            time.sleep(0.5)
    if not mqtt_connected:
        logger.critical(f'Stopped before initial MQTT connect. Exiting.')
        sys.exit(1)

    # Setup HomeAssistant after mqtt client is up
    if deamon_opts['add-to-homeassistant']:
        try:
            HassConnector.publish_hass_autodiscovery(globs.mqtt_client)
        except Exception as e:
            logger.error( f'Error setting up homeassistant autodiscovery: {e}')
 
    # Now comes the real main loop
    current_poller = 0
    while MainControl.run_loop:
        time.sleep(deamon_opts['set-loop-break'])

        modbus_connected = await modbus_master.check_connect()

        for dev in Device.all_devices.values():
            dev.publish_diagnostics()

        if not modbus_connected:
            time.sleep(0.5)
            continue

        try:
            await Poller.all_poller[current_poller].check_poll()

            await Device.process_set_requests(globs.mqtt_client)

            #XXX New reenable logic required
            #anyAct = False
            #for p in Poller.all_poller:
            #    if p.disabled is not True:
            #        anyAct = True
            #if not anyAct:
            #    time.sleep(0.010)
            #    for p in pollers:
            #        if p.disabled == True:
            #            p.disabled = False
            #            p.failcounter = 0
            #            globs.logger.info("Reactivated poller "+p.topic+" with Slave-ID "+str(
            #                p.slaveid) + " and functioncode "+str(p.functioncode)+".")

        except Exception as e:
            logger.error( "Error: "+str(e)+" when polling or publishing, trying again...")

        current_poller = current_poller + 1
        if current_poller == len(Poller.all_poller):
            current_poller = 0
    
    for dev in Device.all_devices.values() :
        dev.disable()
    modbus_master.master.close()

    sys.exit(1)
