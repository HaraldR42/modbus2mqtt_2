import unittest
import struct 
from data_types import DataTypeConversion


class TestDataTypeConversion(unittest.TestCase):

    def test_bool(self):
        bool_conv = DataTypeConversion.get_data_converter("bool")
        self.assertEqual(bool_conv.str2mb_fct("TRUE"), 1)
        self.assertEqual(bool_conv.str2mb_fct("1"), 1)
        self.assertEqual(bool_conv.str2mb_fct("off"), 0)
        self.assertEqual(bool_conv.mb2py_fct(0x0001), True)
        self.assertEqual(bool_conv.mb2py_fct(0x0000), False)
        self.assertEqual(bool_conv.mb2py_fct([0x0001]), True)
        self.assertEqual(bool_conv.mb2py_fct([0x0000]), False)

    def test_int16(self):
        int16_conv = DataTypeConversion.get_data_converter("int16")
        self.assertEqual(int16_conv.str2mb_fct("0x1234"), 0x1234)
        self.assertEqual(int16_conv.str2mb_fct("-4095"), -4095)
        with self.assertRaises(OverflowError):
            int16_conv.str2mb_fct( "0x8000")
        self.assertEqual(int16_conv.mb2py_fct(0x1234), 0x1234)
        self.assertEqual(int16_conv.mb2py_fct(0xfec6), -314)
        self.assertEqual(int16_conv.mb2py_fct([0x1234]), 0x1234)
        self.assertEqual(int16_conv.mb2py_fct([0xfec6]), -314)

    def test_uint16(self):
        uint16_conv = DataTypeConversion.get_data_converter("uint16")
        self.assertEqual(uint16_conv.str2mb_fct( "0x1234"), 0x1234)
        self.assertEqual(uint16_conv.str2mb_fct( "0x8000"), 0x8000)
        with self.assertRaises(OverflowError):
            uint16_conv.str2mb_fct( "-4095")
        self.assertEqual(uint16_conv.mb2py_fct(0x1234), 0x1234)
        self.assertEqual(uint16_conv.mb2py_fct(0xfec6), 0xfec6)
        self.assertEqual(uint16_conv.mb2py_fct([0x1234]), 0x1234)
        self.assertEqual(uint16_conv.mb2py_fct([0xfec6]), 0xfec6)

    def test_int32LE(self):
        int32LE_conv = DataTypeConversion.get_data_converter("int32LE")
        self.assertEqual(int32LE_conv.str2mb_fct( "0x12345678"), [0x1234, 0x5678])
        with self.assertRaises(struct.error):
            int32LE_conv.str2mb_fct( "0xfedcba98")
        self.assertEqual(int32LE_conv.mb2py_fct( [0x1234, 0x5678]), 0x12345678)
        self.assertEqual(int32LE_conv.mb2py_fct( [0xF8A4, 0x6B57]), -123442345)

    def test_int32BE(self):
        int32BE_conv = DataTypeConversion.get_data_converter("int32BE")
        self.assertEqual(int32BE_conv.str2mb_fct( "0x12345678"), [0x5678, 0x1234])
        with self.assertRaises(struct.error):
            int32BE_conv.str2mb_fct( "0xfedcba98")
        self.assertEqual(int32BE_conv.mb2py_fct( [0x1234, 0x5678]), 0x56781234)
        self.assertEqual(int32BE_conv.mb2py_fct( [0x6B57, 0xF8A4]), -123442345)

    def test_uint32LE(self):
        uint32LE_conv = DataTypeConversion.get_data_converter("uint32LE")
        self.assertEqual(uint32LE_conv.str2mb_fct( "0x12345678"), [0x1234, 0x5678])
        self.assertEqual(uint32LE_conv.str2mb_fct( "0xfedcba98"), [0xfedc, 0xba98])
        with self.assertRaises(OverflowError):
            uint32LE_conv.str2mb_fct( "-4095")
        self.assertEqual(uint32LE_conv.mb2py_fct( [0x1234, 0x5678]), 0x12345678)
        self.assertEqual(uint32LE_conv.mb2py_fct( [0xfedc, 0xba98]), 0xfedcba98)

    def test_uint32BE(self):
        uint32BE_conv = DataTypeConversion.get_data_converter("uint32BE")
        self.assertEqual(uint32BE_conv.str2mb_fct( "0x12345678"), [0x5678, 0x1234])
        self.assertEqual(uint32BE_conv.str2mb_fct( "0xfedcba98"), [0xba98, 0xfedc])
        self.assertEqual(uint32BE_conv.mb2py_fct( [0x1234, 0x5678]), 0x56781234)
        self.assertEqual(uint32BE_conv.mb2py_fct( [0xfedc, 0xba98]), 0xba98fedc)

    def test_float32LE(self):
        float32LE_conv = DataTypeConversion.get_data_converter("float32LE")
        self.assertEqual(float32LE_conv.str2mb_fct( "3.1415926"), [0x4049, 0x0fda])
        self.assertEqual(float32LE_conv.str2mb_fct( "-3.1415926"), [0xc049, 0x0fda])
        self.assertAlmostEqual(float32LE_conv.mb2py_fct( [0x4049, 0x0fda]), 3.1415926, 6)
        self.assertAlmostEqual(float32LE_conv.mb2py_fct( [0xc049, 0x0fda]), -3.1415926, 6)

    def test_float32BE(self):
        float32BE_conv = DataTypeConversion.get_data_converter("float32BE")
        self.assertEqual(float32BE_conv.str2mb_fct( "3.1415926"), [0x0fda, 0x4049])
        self.assertEqual(float32BE_conv.str2mb_fct( "-3.1415926"), [0x0fda, 0xc049])
        self.assertAlmostEqual(float32BE_conv.mb2py_fct( [0x0fda, 0x4049]), 3.1415926, 6)
        self.assertAlmostEqual(float32BE_conv.mb2py_fct( [0x0fda, 0xc049]), -3.1415926, 6)


if __name__ == '__main__':
    unittest.main()
