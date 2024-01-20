import csv
import yaml

from .globals import logger, deamon_opts, device_opts, poller_opts, ref_opts
from .modbus_objects import ModbusMaster,Device,Poller,Reference
from .mqtt_client import MqttClient
from .home_assistant import HassDevice, HassEntity

#
# Global counter for errors during parsing config files
#
config_error_count = 0


###################################################################################################################
#
# Helper class
#

class ConfigSource:
    def __init__(self, file, line:str=None):
        self.file_name = file.name
        self.line = line
    def __str__(self):
        if self.line:
            return f'file:{self.file_name}, line: {self.line}'
        else:
            return f'file:{self.file_name}'


###################################################################################################################
#
# Parsing YAML config files
#

class ConfigYaml:
    
    def print_yaml_options() -> None:
        root = { }
        root['Daemon'] = dict(deamon_opts)
        dev= dict(device_opts)
        root['Devices'] = [ dev ]
        root['Devices'][0]['Pollers'] = [ dict(poller_opts) ]
        root['Devices'][0]['Pollers'][0]['References'] = [ dict(ref_opts) ]
        print( yaml.dump(root,sort_keys=False))
        

    def read_daemon_config(yaml_file) -> None:
        global config_error_count
        try:
            yaml_file.seek(0)
            yaml_dict = yaml.safe_load(yaml_file)
        except Exception as e:
            logger.error( f'Config error ({ConfigSource( yaml_file)}): {e}')
            config_error_count += 1
            return

        if 'Daemon' not in yaml_dict:
            return        
        daemon_part = yaml_dict['Daemon']

        for key in daemon_part:
            if key not in deamon_opts:
                logger.error( f'Unknown yaml daemon option "{key}"')
                config_error_count += 1
                continue
            deamon_opts[key] = daemon_part[key]


    def read_devices( yaml_file, mqttc:MqttClient, modbus_master:ModbusMaster) -> None:        
        global config_error_count
        config_source = ConfigSource( yaml_file)
        try:
            yaml_file.seek(0)
            yaml_dict = yaml.safe_load(yaml_file)
        except Exception as e:
            logger.error( f'Config error ({config_source}): {e}')
            config_error_count += 1
            return

        # pop an throw away the daemon options
        yaml_dict.pop('Daemon', None)

        # pop all devices
        devices_list = yaml_dict.pop('Devices',[])
        if len(devices_list) == 0:
            logger.warning( f'No devices defined ({config_source})')
        for dev in devices_list:
            ConfigYaml._parse_device_dict( dev, config_source, mqttc, modbus_master)

        # the remaining options are errnous
        for key in yaml_dict:
            logger.error( f'Unknown yaml option "{key}" ({config_source})')
            config_error_count += 1


    def _parse_device_dict(dev_dict:dict, config_source:ConfigSource, mqttc:MqttClient, modbus_master:ModbusMaster) -> None:
        global config_error_count
        this_dev_opts = dict(device_opts) # create our own copy to make changes
        this_hass_dev_opts = dict(HassDevice.get_config_options()) # create our own copy to make changes
        default_poller_opts = dict(poller_opts)

        # pop all device options and hass-device options
        for dev_key in list(dev_dict):
            if dev_key in this_dev_opts:
                this_dev_opts[dev_key] = dev_dict.pop(dev_key)
            elif dev_key in this_hass_dev_opts:
                this_hass_dev_opts[dev_key] = dev_dict.pop(dev_key)
            elif dev_key.startswith('Default-') and (dev_key.removeprefix('Default-') in default_poller_opts):
                default_poller_opts[dev_key.removeprefix('Default-')] = dev_dict.pop(dev_key)

        try:
            the_dev_name = this_dev_opts['name']
            the_dev_id = this_dev_opts['slave-id']
            new_device = Device(config_source, mqttc, modbus_master, the_dev_name, the_dev_id, this_hass_dev_opts)
        except Exception as e:
            logger.error( f'Config error parsing device {the_dev_name} ({config_source}): {e}')
            config_error_count += 1
            return

        # pop all pollers
        pollers_list = dev_dict.pop('Pollers', [])
        for poller in pollers_list:
            ConfigYaml._parse_poller_dict( poller, default_poller_opts, config_source, new_device, mqttc)
        if len(pollers_list) == 0:
            logger.warning( f'No pollers defined for device {new_device.name}')

        # the remaining options are errnous
        local_errors = 0
        for dev_key in dev_dict:
            logger.error( f'Unknown yaml device option "{dev_key}"')
            local_errors += 1
        config_error_count += local_errors


    def _parse_poller_dict(poller_dict:dict, default_poller_opts:dict, config_source:ConfigSource, curr_device:Device, mqttc:MqttClient) -> None:
        global config_error_count
        this_poller_opts = dict(default_poller_opts) # create our own copy to make changes
        this_default_ref_opts = dict(ref_opts) # create our own copy to make changes
        this_default_hass_opts = HassEntity.get_all_config_opts() # create our own copy to make changes

        # pop all poller options, default reference options and default hass-reference options
        for poller_key in list(poller_dict):
            if poller_key in this_poller_opts:
                this_poller_opts[poller_key] = poller_dict.pop(poller_key)
            elif poller_key.startswith('Default-') and (poller_key.removeprefix('Default-') in this_default_ref_opts):
                this_default_ref_opts[poller_key.removeprefix('Default-')] = poller_dict.pop(poller_key)
            elif poller_key.startswith('Default-') and (poller_key.removeprefix('Default-') in this_default_hass_opts):
                this_default_hass_opts[poller_key.removeprefix('Default-')] = poller_dict.pop(poller_key)

        try:
            start_reg = this_poller_opts['start-reg']
            len_regs = this_poller_opts['len-regs']
            reg_type = this_poller_opts['reg-type']
            poll_rate = this_poller_opts['poll-rate']
            new_poller = Poller( config_source, curr_device, start_reg, len_regs, reg_type, poll_rate)
        except Exception as e:
            logger.error( f'Config error parsing poller in device {curr_device.name} ({config_source}): {e}')
            config_error_count += 1
            return

        # pop all references
        references_list = poller_dict.pop('References', [])
        if len(references_list) == 0:
            logger.warning( f'No references defined for device {curr_device.name}')
        for reference in references_list:
            ConfigYaml._parse_reference_dict( reference, this_default_ref_opts, this_default_hass_opts, config_source, new_poller, mqttc)

        # the remaining options are errnous
        local_errors = 0
        for poller_key in poller_dict:
            logger.error( f'Unknown yaml poller option "{poller_key}" in device {curr_device.name}')
            local_errors += 1
        config_error_count += local_errors


    def _parse_reference_dict(reference_dict:dict, default_ref_opts:dict, all_default_hass_opts:dict, config_source:ConfigSource, curr_poller:Poller, mqttc:MqttClient) -> None:
        global config_error_count
        this_ref_opts = dict(default_ref_opts) # create our own copy to make changes
        # pop all reference options
        for ref_key in list(reference_dict):
            if ref_key in this_ref_opts:
                this_ref_opts[ref_key] = reference_dict.pop(ref_key)

        # identify all valid hass options dependant on entity-type and copy the relevant defaults from level above
        this_hass_ref_opts = dict()
        try:
            for ref_key, config_default_val in HassEntity.get_valid_config_opts( this_ref_opts['hass_entity_type']).items():
                this_hass_ref_opts[ref_key] = all_default_hass_opts[ref_key] if ref_key in all_default_hass_opts else config_default_val
        except Exception as e:
            logger.error( f'Config error parsing reference in device/referece {curr_poller.device.name}/{this_ref_opts["topic"]} ({config_source}): {e}')
            config_error_count += 1
            return
        # pop all valid hass options
        for ref_key in list(reference_dict):
            if ref_key in this_hass_ref_opts:
                this_hass_ref_opts[ref_key] = reference_dict.pop(ref_key)
                
        try:
            topic = this_ref_opts['topic']
            start_reg = this_ref_opts['start-reg']
            write_reg = this_ref_opts['write-reg']
            is_readable = this_ref_opts['readable']
            is_writeable = this_ref_opts['writeable']
            data_type = this_ref_opts['data-type']
            scaling = this_ref_opts['scaling']
            format_str = this_ref_opts['format-str']
            hass_entity_type = this_ref_opts['hass_entity_type']
            if not is_readable and not is_writeable:
                logger.error(f'Reference neither readable nor writeable. Ignoring device/referece {curr_poller.device.name}/{this_ref_opts["topic"]}.')
                config_error_count += 1
                return
            new_ref = Reference( config_source, mqttc, curr_poller, topic, start_reg, write_reg, is_readable, is_writeable, data_type, scaling, format_str, hass_entity_type, this_hass_ref_opts)
        except Exception as e:
            logger.error( f'Config error parsing device/referece {curr_poller.device.name}/{this_ref_opts["topic"]} ({config_source}): {e}')
            config_error_count += 1
            return

        # the remaining options are errnous
        local_errors = 0
        for ref_key in reference_dict:
            logger.error( f'Unknown/illegal yaml reference option in device/referece {curr_poller.device.name}/{this_ref_opts["topic"]}')
            local_errors += 1
        config_error_count += local_errors


###################################################################################################################
#
# Parsing legacy CSV config files
#

class ConfigSpicierCsv:

    # CSV file format:
    #    0,          1,        2,        3,        4,       5,         6
    # poll,    devName,  slaveId, startReg,  lenRegs, regType,  pollRate
    #  ref,  topicName, startReg,       rw, dataType, scaling, formatStr

    def read_devices( csv_file, mqttc:MqttClient, modbus_master:ModbusMaster) -> None:        
        with csv_file as csvfile:
            csvfile.seek(0)
            reader = csv.reader(csvfile, quoting=csv.QUOTE_ALL, skipinitialspace=True)
            curr_device = None
            curr_poller = None
            for row in reader:
                if len(row) == 0 :
                    continue
                line_num = reader.line_num
                line_type = row[0].lower()

                if line_type == "poller" or line_type == "poll":
                    curr_poller = ConfigSpicierCsv._parse_poller_line(row, ConfigSource( csv_file, line_num), mqttc, modbus_master)
                elif line_type == "reference" or line_type == "ref":
                    ConfigSpicierCsv._parse_reference_line(row, ConfigSource( csv_file, line_num), curr_poller, mqttc)
                else:
                    pass # simply ignore every other line type


    def _parse_poller_line(row, config_source:ConfigSource, mqttc:MqttClient, modbus_master:ModbusMaster) -> Poller:
        global config_error_count
        try:
            device_name = str(row[1])
            slaveid = int(row[2])
            start_reg = int(row[3])
            len_regs = int(row[4])
            reg_type = str(row[5])
            poll_rate = float(row[6])

            if device_name in Device.all_devices:
                the_dev:Device = Device.all_devices[device_name]
                if the_dev.slaveid != slaveid:
                    raise ValueError(f'Conflicting poller lines, same topic {device_name} but different slaveid {the_dev.slaveid} vs. {slaveid}.')
            else:
                the_dev = Device(config_source, mqttc, modbus_master, device_name, slaveid)

            poller = Poller( config_source, the_dev, start_reg, len_regs, reg_type, poll_rate)
            return poller
        except Exception as e:
            logger.error( f'Config error ({config_source}): {e}')
            config_error_count += 1
            return None


    def _parse_reference_line(row, config_source:ConfigSource, curr_poller:Poller, mqttc:MqttClient) -> Reference:
        global config_error_count
        if curr_poller is None:
            logger.error( f'No poller defined. Ignoring reference in {config_source}.')
            config_error_count += 1
            return

        try:
            topic = row[1]
            start_reg = int(row[2])
            rw = row[3]
            data_type = row[4] if len(row)>4 else None
            scaling = float(row[5]) if len(row)>5 else None
            #format_str = row[6] if len(row)>6 else None

            is_readable = True if "r" in rw else False
            is_writeable = True if "w" in rw else False

            if not is_readable and not is_writeable:
                logger.error(f'Reference neither readable nor writeable. Ignoring reference in {config_source}.')
                config_error_count += 1
                return
            
            new_ref = Reference( config_source, mqttc, curr_poller, topic, start_reg, is_readable, is_writeable, data_type, scaling, None)

        except Exception as e:
            logger.error( f'Config error ({config_source}): {e}')
            config_error_count += 1
            return None
