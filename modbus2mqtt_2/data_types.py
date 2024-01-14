import struct


###################################################################################################################
#
# Class for conrete data converter being sent to the reference
#

class DataConverter:
    def __init__(self, type:str, base_type_reg_cnt:int, list_length:int, reg_cnt:int, str2mb_fct, mb2py_fct):
        self.type = type
        self.base_type_reg_cnt = base_type_reg_cnt
        self.list_length = list_length
        self.reg_cnt = reg_cnt
        self.str2mb_fct = str2mb_fct
        self.mb2py_fct = mb2py_fct


###################################################################################################################
#
# Class for conrete data converter being sent to the reference
#

class DataTypeConversion:

    _reg_cnt_dict = {    
        "bool":      1,
        "int16":     1,
        "uint16":    1,
        "int32LE":   2,
        "int32BE":   2,
        "uint32LE":  2,
        "uint32BE":  2,
        "float32LE": 2,
        "float32BE": 2,
    }

    _str2mb_dict = {    
        "bool":      lambda str: DataTypeConversion._str2modbus_bool(str),
        "int16":     lambda str: struct.unpack( ">h", int.to_bytes(int(str,0), length=2, signed=True))[0],
        "uint16":    lambda str: struct.unpack( ">H", int.to_bytes(int(str,0), length=2, signed=False))[0],
        "int32LE":   lambda str : (lambda b1, b2, b3, b4 : [(b1<<8)|b2,(b3<<8)|b4])(*struct.pack( ">i", int(str,0))),
        "int32BE":   lambda str : (lambda b1, b2, b3, b4 : [(b3<<8)|b4,(b1<<8)|b2])(*struct.pack( ">i", int(str,0))),
        "uint32LE":  lambda str : (lambda b1, b2, b3, b4 : [(b1<<8)|b2,(b3<<8)|b4])(*int.to_bytes(int(str,0), length=4, signed=False, byteorder='big')),
        "uint32BE":  lambda str : (lambda b1, b2, b3, b4 : [(b3<<8)|b4,(b1<<8)|b2])(*int.to_bytes(int(str,0), length=4, signed=False, byteorder='big')),
        "float32LE": lambda str : (lambda b1, b2, b3, b4 : [(b1<<8)|b2,(b3<<8)|b4])(*struct.pack(">f", float(str))),
        "float32BE": lambda str : (lambda b1, b2, b3, b4 : [(b3<<8)|b4,(b1<<8)|b2])(*struct.pack(">f", float(str))),
    }

    _mb2py_dict = {    
        "bool":      lambda val: bool(val[0] if isinstance(val,list) else val),
        "int16":     lambda val: struct.unpack( ">h", int(val[0] if isinstance(val,list) else val).to_bytes(length=2))[0],
        "uint16":    lambda val: struct.unpack( ">H", int(val[0] if isinstance(val,list) else val).to_bytes(length=2))[0],
        "int32LE":   lambda val: struct.unpack( ">i", int((val[0]<<16) | val[1]).to_bytes(length=4))[0],
        "int32BE":   lambda val: struct.unpack( ">i", int(val[0] | (val[1]<<16)).to_bytes(length=4))[0],
        "uint32LE":  lambda val: (val[0]<<16) | val[1],
        "uint32BE":  lambda val: val[0] | (val[1]<<16),
        "float32LE": lambda val: struct.unpack('=f', struct.pack('=I',int(val[0])<<16|int(val[1])))[0],
        "float32BE": lambda val: struct.unpack('=f', struct.pack('=I',int(val[1])<<16|int(val[0])))[0],
    }


    def get_data_converter(type:str) -> DataConverter:
        if type is None or type == "":
            type="uint16"

        if type in DataTypeConversion._reg_cnt_dict:
            base_type_reg_cnt = DataTypeConversion._reg_cnt_dict[type]
            list_length = 1
            reg_cnt = base_type_reg_cnt*list_length
            str2mb_fct = DataTypeConversion._str2mb_dict[type]
            mb2py_fct = DataTypeConversion._mb2py_dict[type]

        #elif type.startswith('list-'):  # list-<baseType>-<length>
        #    try:
        #        base_type, list_length = itemgetter(1,2)(type.split(sep='-'))
        #        list_length = int(list_length)
        #    except:
        #        raise ValueError("Malformed type '"+type+"'.")
        #    if base_type not in DataTypeConversion.reg_cnt_dict:
        #        raise ValueError("Base type '"+base_type+"' of type '"+type+"' unknown.")
        #    base_type_reg_cnt = DataTypeConversion.reg_cnt_dict[base_type]
        #    reg_cnt = base_type_reg_cnt*list_length
        #    str2mb_fct = None
        #    mb2py_fct = None

        #elif type.startswith('string'):  # string<charLength>
        #    try:
        #        char_len = int(type.removeprefix('string'))
        #    except:
        #        raise ValueError("Malformed type '"+type+"'.")
        #    if (char_len%2) != 0:
        #        raise ValueError("Odd length in type '"+type+"'.")
        #    base_type_reg_cnt = 0.5
        #    list_length = char_len
        #    reg_cnt = base_type_reg_cnt*list_length
        #    str2mb_fct = None
        #    mb2py_fct = None

        else:
            raise ValueError(f'Unknown data type "{type}".')

        return DataConverter(type, base_type_reg_cnt, list_length, reg_cnt, str2mb_fct, mb2py_fct)


    def _str2modbus_bool(payload:str) -> bool:
        payload=str(payload)
        if payload.lower() == 'true' or payload=='1' or payload.lower()=='on' or payload.lower()=='yes':
            value = True
        elif payload.lower() == 'false' or payload=='0' or payload.lower()=='off' or payload.lower()=='no':
            value = False
        else:
            raise ValueError( "Cannot interpret '"+payload+"' as 'bool'.")
        return bool(value)


#class DataTypes_OLD:
#
#    def parseString(refobj,msg):
#        out=[]
#        if len(msg)<=refobj.stringLength:
#            for x in range(1,len(msg)+1):
#                if math.fmod(x,2)>0:
#                    out.append(ord(msg[x-1])<<8)
#                else:
#                    pass
#                    out[int(x/2-1)]+=ord(msg[x-1])
#        else:
#            out = None
#        return out
#    def combineString(refobj,val):
#        out=""
#        for x in val:
#            out+=chr(x>>8)
#            out+=chr(x&0x00FF)
#        return out
#
#
#    def parseListUint16(refobj,msg):
#        out=[]
#        try:
#            msg=msg.rstrip()
#            msg=msg.lstrip()
#            msg=msg.split(" ")
#            if len(msg) != refobj.regAmount:
#                return None
#            for x in range(0, len(msg)):
#                out.append(int(msg[x]))
#        except:
#            return None
#        return out
#    def combineListUint16(refobj,val):
#        out=""
#        for x in val:
#            out+=str(x)+" "
#        return out
#
#    def parseDataType(refobj,conf):
#        if conf is None or conf == "uint16" or conf == "":
#            refobj.regAmount=1
#            refobj.parse=DataTypes.parseuint16
#            refobj.combine=DataTypes.combineuint16
#        elif conf.startswith("list-uint16-"):
#            try:
#                length = int(conf[12:15])
#            except:
#                length = 1
#            if length > 50:
#                print("Data type list-uint16: length too long")
#                length = 50
#            refobj.parse=DataTypes.parseListUint16
#            refobj.combine=DataTypes.combineListUint16
#            refobj.regAmount=length
#        elif conf.startswith("string"):
#            try:
#                length = int(conf[6:9])
#            except:
#                length = 2
#            if length > 100:
#                print("Data type string: length too long")
#                length = 100
#            if  math.fmod(length,2) != 0:
#                length=length-1
#                print("Data type string: length must be divisible by 2")
#            refobj.parse=DataTypes.parseString
#            refobj.combine=DataTypes.combineString
#            refobj.stringLength=length
#            refobj.regAmount=int(length/2)
#