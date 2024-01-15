import struct


###################################################################################################################
#
# Class for data convertion
#

class DataConverter:

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
        "bool":      lambda self, str : self._str2modbus_bool(str),
        "int16":     lambda self, str : struct.unpack( ">h", int.to_bytes(int(str,0), length=2, signed=True))[0],
        "uint16":    lambda self, str : struct.unpack( ">H", int.to_bytes(int(str,0), length=2, signed=False))[0],
        "int32LE":   lambda self, str : (lambda b1, b2, b3, b4 : [(b1<<8)|b2,(b3<<8)|b4])(*struct.pack( ">i", int(str,0))),
        "int32BE":   lambda self, str : (lambda b1, b2, b3, b4 : [(b3<<8)|b4,(b1<<8)|b2])(*struct.pack( ">i", int(str,0))),
        "uint32LE":  lambda self, str : (lambda b1, b2, b3, b4 : [(b1<<8)|b2,(b3<<8)|b4])(*int.to_bytes(int(str,0), length=4, signed=False, byteorder='big')),
        "uint32BE":  lambda self, str : (lambda b1, b2, b3, b4 : [(b3<<8)|b4,(b1<<8)|b2])(*int.to_bytes(int(str,0), length=4, signed=False, byteorder='big')),
        "float32LE": lambda self, str : (lambda b1, b2, b3, b4 : [(b1<<8)|b2,(b3<<8)|b4])(*struct.pack(">f", float(str))),
        "float32BE": lambda self, str : (lambda b1, b2, b3, b4 : [(b3<<8)|b4,(b1<<8)|b2])(*struct.pack(">f", float(str))),
    }

    _mb2py_dict = {    
        "bool":      lambda self, val : bool(val[0] if isinstance(val,list) else val),
        "int16":     lambda self, val : struct.unpack( ">h", int(val[0] if isinstance(val,list) else val).to_bytes(length=2))[0],
        "uint16":    lambda self, val : struct.unpack( ">H", int(val[0] if isinstance(val,list) else val).to_bytes(length=2))[0],
        "int32LE":   lambda self, val : struct.unpack( ">i", int((val[0]<<16) | val[1]).to_bytes(length=4))[0],
        "int32BE":   lambda self, val : struct.unpack( ">i", int(val[0] | (val[1]<<16)).to_bytes(length=4))[0],
        "uint32LE":  lambda self, val : (val[0]<<16) | val[1],
        "uint32BE":  lambda self, val : val[0] | (val[1]<<16),
        "float32LE": lambda self, val : struct.unpack('=f', struct.pack('=I',int(val[0])<<16|int(val[1])))[0],
        "float32BE": lambda self, val : struct.unpack('=f', struct.pack('=I',int(val[1])<<16|int(val[0])))[0],
    }

    def __init__(self, type:str):
        self.type = "uint16" if type is None or type == "" else type
        self.base_type_reg_cnt = 0
        self.list_length = 0
        self.reg_cnt = 0
        self._str2mb_fct = None
        self._mb2py_fct = None

        if self.type in DataConverter._reg_cnt_dict:
            self.base_type_reg_cnt = DataConverter._reg_cnt_dict[self.type]
            self.list_length = 1
            self.reg_cnt = self.base_type_reg_cnt*self.list_length
            self._str2mb_fct = DataConverter._str2mb_dict[self.type]
            self._mb2py_fct = DataConverter._mb2py_dict[self.type]

        elif self.type.startswith('string'):  # string<charLength>
            try:
                char_len = int(self.type.removeprefix('string'))
            except:
                raise ValueError(f'Malformed string type {self.type}')
            if (char_len%2) != 0:
                raise ValueError(f'String length not even in {self.type}')
            self.base_type_reg_cnt = 0.5
            self.list_length = char_len
            self.reg_cnt = int(self.base_type_reg_cnt*self.list_length)
            self._str2mb_fct = lambda self, val: self._str2modbus_string(val)
            self._mb2py_fct = lambda self, val: self._mb2py_string(val)

        else:
            raise ValueError(f'Unknown data type "{self.type}".')

    def str2mb(self, string):
        return self._str2mb_fct(self, string)

    def mb2py(self, val):
        return self._mb2py_fct(self, val)


    def _str2modbus_bool(self, payload:str) -> bool:
        payload=str(payload)
        if payload.lower() == 'true' or payload=='1' or payload.lower()=='on' or payload.lower()=='yes':
            value = True
        elif payload.lower() == 'false' or payload=='0' or payload.lower()=='off' or payload.lower()=='no':
            value = False
        else:
            raise ValueError(f'Cannot interpret "{payload}" as bool.')
        return bool(value)


    def _str2modbus_string(self, payload:str):
        out=[]
        if payload.length > self.list_length:
            raise ValueError( f'String "{payload}" too long for {self.reg_cnt} modbus registers')
        for a in range(self.reg_cnt):
            b0 = (ord(payload[2*a])&0xff)<<8 if len(payload)>2*a else 0x00
            b1 = (ord(payload[2*a+1])&0xff) if len(payload)>2*a+1 else 0x00
            out.append( b0&b1)
        return out

    def _mb2py_string(self, val):
        out=''
        for x in val:
            if x&0x00FF != 0:
                out += chr(x&0x00FF)
            if x>>8 != 0:
                out += chr(x>>8)
        return out




###################################################################################################################

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

#class DataTypes_OLD:
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
