import logging
import socket

__version__ = "0.3.0"
__myname__ = "modbus2mqtt_2"
__myname_short__ = "m2m"
__min_version__ = (3,11)

logging.basicConfig()
logger = logging.getLogger('main-logger')


###################################################################################################################
#
# Following dicts serve three purposes:
#   - Definition of yaml configuration options
#   - Provide default value for each option
#   - Store the actual values of options after parsing the config files
#
# For additional Home Assistant specific options see home_assistant.py
#

# Configuration options for daemon section with default values
deamon_opts = {
    'config':                   None,
    'rtu':                      None,               # pyserial URL (or port name) for RTU serial port
    'tcp':                      None,               # Act as a Modbus TCP master, connecting to host TCP

    # MQTT broker options: All options for connecting to an MQTT broker
    'mqtt-host':                'localhost',        # MQTT server address. Defaults to "localhost"
    'mqtt-port':                None,               # Defaults to 8883 for TLS or 1883 for non-TLS
    'mqtt-clientid':            f'mb2mqtt-{socket.gethostname().split(".")[0]}',
    'mqtt-user':                None,               # Username for authentication (optional)
    'mqtt-pass':                "",                 # Password for authentication (optional)
    'mqtt-use-tls':             False,              # Use TLS
    'mqtt-insecure':            False,              # Use TLS without providing certificates
    'mqtt-cacerts':             None,               # Path to keychain
    'mqtt-tls-version':         None,               # TLS protocol version, can be one of tlsv1.2 tlsv1.1 or tlsv1

    # MQTT publish options: All options influencing the MQTT related behaviour
    'mqtt-topic':               'modbus/',          # Topic prefix to be used for subscribing/publishing. Defaults to "modbus/"
    'mqtt-value-qos':           0,                  # QoS value for publishing values. Defaults to 0
    'publish-seconds':          300,                # Publish values after n seconds (0=always), even if they did not change.
    'retain-values':            False,              # Set retain flag for published modbus values.

    # Modbus connection options: All options influencing the Modbus connection related behaviour
    'rtu-baud':                 19200,              # Baud rate for serial port. Defaults to 19200
    'rtu-parity':               'even',             # Parity for serial port ('even', 'odd', 'none). Defaults to even
    'tcp-port':                 502,                # Port for MODBUS TCP. Defaults to 502

    # Modbus running options: Modbus related options during running
    'set-modbus-timeout':       1.0,                # Response time-out for Modbus devices
    'avoid-fc6':                False,              # If set, use function code 16 (write multiple registers) even when just writing a single register

    # Misc options
    'diagnostics-rate':         0,                  # Time in seconds after which for each device diagnostics are published via mqtt. Set to sth. like 600 (= every 10 minutes) or so.
    'add-to-homeassistant':     False,              # Add devices to Home Assistant using Home Assistant\'s MQTT-Discovery
    'hass-discovery-prefix':    'homeassistant',    # Add devices to Home Assistant using Home Assistant\'s MQTT-Discovery
    'verbosity':                'info',             # Verbosity level ('debug', 'info', 'warning', 'error', 'critical')
}

# Configuration options for device section with default values
device_opts = {
    'name':         None,   # The name of the device.
    'slave-id':     None,   # Modbus slave address
}

# Configuration options for poller section with default values
poller_opts = {
    'start-reg':    None,
    'len-regs':     1,
    'reg-type':     'coil',
    'poll-rate':    15.0,   
}

# Configuration options for reference section with default values
ref_opts = {
    'topic':                None,
    'start-reg':            None, # if undefined, the poller's start-reg will be used
    'write-reg':            None,
    'readable':             True,
    'writeable':            False,
    'data-type':            None, # if undefined, a default depending on the poller type will be used
    'scaling':              None,
    'format-str':           None,
    'hass_entity_type':     None,
}
