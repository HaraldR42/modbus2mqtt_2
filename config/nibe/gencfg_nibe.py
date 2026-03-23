import csv
import os
from dataclasses import InitVar, dataclass, field, fields
from pathlib import Path
import re
from typing import Dict, List
from enum import Enum
import math
import yaml


class Defaults:
    ENUM_UNKNOWN_VALUE = 'Unknown'


# Decorator to ensure a method is only run once per class, not per instance
def classinit(fn):
    attr = f'_run_once_{fn.__name__}'
    def wrapper(self, *args, **kwargs):
        if not getattr(type(self), attr, False):
            setattr(type(self), attr, True)
            return fn(self, *args, **kwargs)
    return wrapper


# Enum for register types
class RegisterType(Enum):
    NONE = 'NONE'
    INPUT_REGISTER = 'MODBUS_INPUT_REGISTER'
    HOLDING_REGISTER = 'MODBUS_HOLDING_REGISTER'


@dataclass
class NibeModbusRegister:

    csv_dict: InitVar[dict[str,str]]

    # Own fields
    key: str = field(default=None)
    nibe_default: bool = field(default=None)
    intervall: float = field(default=None)
    disabled: bool = field(default=None)
    device: str = field(default=None)
    subdevice: str = field(default=None)
    enum: Dict[str, str] = field(default=None)
    comment: str = field(default=None)
    relevant: bool = field(default=None)

    # Nibe fields
    titel: str = field(default=None)
    registertyp: RegisterType = field(default=None)
    register: int = field(default=None)
    divisionsfaktor: str = field(default=None)
    einheit: str = field(default=None)
    variablengrosse: str = field(default=None)
    mindestwert: str = field(default=None)
    hoechstwert: str = field(default=None)
    standardwert: str = field(default=None)


    @classmethod
    def read_nibe_csv(cls, csv_file: str) -> Dict[str, 'NibeModbusRegister']:
        registers = {}
        
        # Ensure file exists
        if not os.path.exists(csv_file):
            print(f'Error: File {csv_file} not found')
            return registers
        
        with open(csv_file, 'r', encoding='utf-8') as file:
            cleaned = (re.sub(r'[\xad\ufeff]', '', line) for line in file)
            reader = csv.DictReader(cleaned, delimiter=';')
            for row in reader:
                if not row:
                    continue
                register_obj = cls(csv_dict=row)
                registers[register_obj.key] = register_obj
        return registers


    def __post_init__(self, csv_dict: dict[str, str]):
        def csv_get_float(field: str) -> float|None:
            value = csv_dict.get(field, '')
            if value is None or value == '':
                return None
            try:
                float(value)
                return float(value)
            except (ValueError, TypeError):
                return None

        def csv_get_bool(field: str) -> bool:
            return True if csv_dict.get(field, '').lower().strip() in ['true', '1', 'yes', 'x'] else False

        self.key = csv_dict.get('Key', '')
        self.nibe_default = csv_get_bool('NIBE-Default')
        self.intervall = csv_get_float('Intervall')
        self.disabled = csv_get_bool('Disabled')
        self.device = csv_dict.get('Device', '')
        self.subdevice = csv_dict.get('Subdevice', '')

        enum_yaml = csv_dict.get('Enum', None)
        if enum_yaml:
            self.enum = yaml.safe_load(enum_yaml)
            if not isinstance(self.enum, dict):
                print(f'Warning: Enum field is not a dict for key {csv_dict.get("Key", "")}')
                self.enum = None
            if not self.enum.get('*', None):
                self.enum['*'] = Defaults.ENUM_UNKNOWN_VALUE

        self.comment = csv_dict.get('Comment', '')
        self.relevant = csv_get_bool('Relevant')

        self.titel = csv_dict.get('Titel', '')
        self.registertyp = RegisterType(csv_dict.get('Registertyp', ''))
        self.register = int(csv_dict.get('Register', '')) if csv_dict.get('Register', '').isdigit() else 0
        self.divisionsfaktor = csv_dict.get('Divisionsfaktor', '')
        self.einheit = csv_dict.get('Einheit', '')
        self.variablengrosse = csv_dict.get('Variablengröße', '')
        self.mindestwert = csv_dict.get('Mindestwert', '')
        self.hoechstwert = csv_dict.get('Höchstwert', '')
        self.standardwert = csv_dict.get('Standardwert', '')


@dataclass
class CustomYamlDataclass:
    @classinit
    def class_init(self):
        yaml.add_representer(self.__class__, self.__class__._representer)

    def __post_init__(self):
        self.class_init()

    @staticmethod
    def _representer(dumper: yaml.Dumper, obj: 'DataPointEntry') -> yaml.MappingNode:
        kv_data = dict()
        for f in fields( obj):
            value = getattr(obj, f.name)
            key = f.metadata['yaml_key'] if 'yaml_key' in f.metadata else f.name
            if value==None or key==None:
                continue
            kv_data[key] = value
        return dumper.represent_mapping( yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, kv_data)


@dataclass
class DataPointEntry(CustomYamlDataclass):

    register: InitVar[NibeModbusRegister]

    start_reg: int = field(default=None, metadata={'yaml_key': 'start-reg'})
    topic: str = field(default=None)
    data_type: str = field(default=None, metadata={'yaml_key': 'data-type'})
    scaling: float = field(default=None)
    format_str: str = field(default=None, metadata={'yaml_key': 'format-str'})
    hass_entity_type: str = field(default=None)
    state_class: str = field(default=None)
    device_class: str = field(default=None)
    unit_of_measurement: str = field(default=None)
    poll_rate: float = field(default=None)
    value_template: str = field(default=None)
    options: str = field(default=None)
    enabled_by_default: bool = field(default=None)
    suggested_display_precision: int = field(default=None)

    len_reg: int = field(default=None, metadata={'yaml_key': None}) # do not export to yaml, only used for grouping registers into pollers
    reg_type: str = field(default=None, metadata={'yaml_key': None}) # do not export to yaml, only used for grouping registers into pollers

    def __post_init__(self, register: NibeModbusRegister):
        super().__post_init__()

        self.start_reg = register.register

        self.topic = re.sub(r' \(', '_', register.titel)
        self.topic = re.sub(r'\)', '',  self.topic)
        self.topic = re.sub(r' ', '-',  self.topic)
        self.topic = re.sub(r'ä', 'ae', self.topic)
        self.topic = re.sub(r'Ä', 'Ae', self.topic)
        self.topic = re.sub(r'ö', 'oe', self.topic)
        self.topic = re.sub(r'Ö', 'Oe', self.topic)
        self.topic = re.sub(r'ü', 'ue', self.topic)
        self.topic = re.sub(r'Ü', 'Ue', self.topic)
        self.topic = re.sub(r'ß', 'ss', self.topic)
        self.topic = re.sub(r'[^\-a-zA-Z0-9_]', '', self.topic)
        if register.subdevice:
            self.topic = f'{register.subdevice}_{self.topic}'
        if register.device:
            self.topic = f'{register.device}_{self.topic}'
        self.topic += f'_{register.key}'

        match register.variablengrosse:
            case 'u8':
                self.data_type = 'uint16'
                self.len_reg = 1
            case 'u16':
                self.data_type = 'uint16'
                self.len_reg = 1
            case 'u32':
                self.data_type = 'uint32BE'
                self.len_reg = 2
            case 's8':
                self.data_type = 'int16'
                self.len_reg = 1
            case 's16':
                self.data_type = 'int16'
                self.len_reg = 1
            case 's32':
                self.data_type = 'int32BE'
                self.len_reg = 2
            case _:
                raise ValueError(f'Unknown variablengrosse: {register.variablengrosse}')

        match register.registertyp:
            case RegisterType.INPUT_REGISTER:
                self.reg_type = 'input_register'
            case RegisterType.HOLDING_REGISTER:
                self.reg_type = 'holding_register'
            case _:
                raise ValueError(f'Unknown registertyp: {register.registertyp}')

        self.suggested_display_precision = 0
        if register.divisionsfaktor.isnumeric() and int(register.divisionsfaktor) != 1:
            # Handle division factor logic here
            f = float(register.divisionsfaktor)
            digits = math.ceil(math.log10(f))
            self.scaling = 1.0 / f
            self.suggested_display_precision = digits
            self.format_str = f'%.{digits}f'

        self.hass_entity_type = 'sensor'
        self.state_class = 'measurement'
        match register.einheit:
            case '%':
                self.unit_of_measurement = '%'
            case 'GM':
                self.unit_of_measurement = 'GM'
            case 'rpm':
                self.unit_of_measurement = 'rpm'
            case 'A':
                self.device_class = 'current'
                self.unit_of_measurement = 'A'
            case 'bar':
                self.device_class = 'pressure'
                self.unit_of_measurement = 'bar'
            case '°C':
                self.device_class = 'temperature'
                self.unit_of_measurement = '°C'
            case 'h':
                self.device_class = 'duration'
                self.unit_of_measurement = 'h'
            case 'Hz':
                self.device_class = 'frequency'
                self.unit_of_measurement = 'Hz'
            case 'kWh':
                self.device_class = 'energy'
                self.unit_of_measurement = 'kWh'
                self.state_class = 'total_increasing'
            case 'l/m':
                self.device_class = 'volume_flow_rate'
                self.unit_of_measurement = 'L/min'
            case 'min':
                self.device_class = 'duration'
                self.unit_of_measurement = 'min'
            case '%RH':
                self.device_class = 'humidity'
                self.unit_of_measurement = '%RH'
            case 's':
                self.device_class = 'duration'
                self.unit_of_measurement = 's'
            case 'Tage':
                self.device_class = 'duration'
                self.unit_of_measurement = 'd'
            case 'V':
                self.device_class = 'voltage'
                self.unit_of_measurement = 'V'
            case 'kW':
                self.device_class = 'power'
                self.unit_of_measurement = 'kW'
            case 'W':
                self.device_class = 'power'
                self.unit_of_measurement = 'W'
            case '':
                if register.enum:
                    self.state_class = None
                    self.suggested_display_precision = None
                    self.device_class = 'enum'
                    self.value_template = '{% set kvlist = { '
                    for k, v in register.enum.items():
                        self.value_template += f'"{k}": "{v}", '
                    self.value_template += ' } %}'
                    self.value_template += '{{ kvlist[value] | default(kvlist["*"]) }}'
                    self.options = list(register.enum.values())
                else:
                    pass
            case _:
                raise ValueError(f'Unknown data point type: {register.einheit}')

        self.poll_rate = register.intervall

        if register.disabled:
            self.enabled_by_default = False


@dataclass
class PollerEntry(CustomYamlDataclass):
    start_reg: int = field(metadata={'yaml_key': 'start-reg'})
    len_regs: int = field(metadata={'yaml_key': 'len-regs'})
    reg_type: RegisterType = field(metadata={'yaml_key': 'reg-type'})
    poll_rate: float = field(metadata={'yaml_key': 'poll-rate'})
    data_points: list[DataPointEntry] = field(metadata={'yaml_key': 'References'})


def create_yaml_config(daemon_config: dict, device_config: dict, poller_list: list[PollerEntry]):
    yaml_root = {
        'Daemon': daemon_config,
        'Devices': [ {
            **device_config,
            'Pollers': poller_list
        } ]
    }
    print( yaml.dump(yaml_root, sort_keys=False, default_flow_style=False, allow_unicode=True))


if __name__ == '__main__':
    def find_file(name:str) -> str|None:
        dirs = [
            ".",
            os.path.dirname(__file__),
        ]
        for d in dirs:
            path = Path(d) / name
            if path.is_file():
                return path
        return None

    config_path = find_file('gencfg_nibe_config.yaml')
    if not config_path:
        print('Error: gencfg_nibe_config.yaml not found')
        exit(1)
    with open(config_path, "r", encoding="utf-8") as file:
        yaml_config = yaml.safe_load(file)

    # Read the CSV file
    csv_path = find_file('nibe_modbus-configured.csv')
    if not csv_path:
        print('Error: nibe_modbus-configured.csv not found')
        exit(1)
    nibe_registers = NibeModbusRegister.read_nibe_csv(csv_path)

    # Create poller entries based on the registers
    current_poller = None
    poller_list = []
    for key, reg in sorted(nibe_registers.items()):
        if not reg.relevant:
            continue
        dp = DataPointEntry(register=reg)
        # Check if we can group this data point with the current poller
        if  not current_poller \
            or dp.reg_type != current_poller.reg_type \
            or current_poller.start_reg + current_poller.len_regs != dp.start_reg \
            or dp.poll_rate != current_poller.poll_rate:
                current_poller = PollerEntry(start_reg=dp.start_reg, len_regs=dp.len_reg, reg_type=dp.reg_type, poll_rate=dp.poll_rate, data_points=[dp])
                poller_list.append(current_poller)
        else:
            current_poller.len_regs += dp.len_reg
            current_poller.data_points.append(dp)
        
    create_yaml_config(daemon_config=yaml_config['Daemon'], device_config=yaml_config['Device'], poller_list=poller_list)