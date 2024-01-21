#
# run with:  python -m unittest
#

import unittest
import struct 
from ..data_types import DataConverter


class TestDataTypeConversion(unittest.TestCase):

    def test_bool(self):
        bool_conv = DataConverter("bool")
        self.assertEqual(bool_conv.str2mb("TRUE"), 1)
        self.assertEqual(bool_conv.str2mb("1"), 1)
        self.assertEqual(bool_conv.str2mb("off"), 0)
        self.assertEqual(bool_conv.mb2py(0x0001), True)
        self.assertEqual(bool_conv.mb2py(0x0000), False)
        self.assertEqual(bool_conv.mb2py([0x0001]), True)
        self.assertEqual(bool_conv.mb2py([0x0000]), False)

    def test_int16(self):
        int16_conv = DataConverter("int16")
        self.assertEqual(int16_conv.str2mb("0x1234"), 0x1234)
        self.assertEqual(int16_conv.str2mb("-4095"), -4095)
        with self.assertRaises(OverflowError):
            int16_conv.str2mb( "0x8000")
        self.assertEqual(int16_conv.mb2py(0x1234), 0x1234)
        self.assertEqual(int16_conv.mb2py(0xfec6), -314)
        self.assertEqual(int16_conv.mb2py([0x1234]), 0x1234)
        self.assertEqual(int16_conv.mb2py([0xfec6]), -314)

    def test_uint16(self):
        uint16_conv = DataConverter("uint16")
        self.assertEqual(uint16_conv.str2mb( "0x1234"), 0x1234)
        self.assertEqual(uint16_conv.str2mb( "0x8000"), 0x8000)
        with self.assertRaises(OverflowError):
            uint16_conv.str2mb( "-4095")
        self.assertEqual(uint16_conv.mb2py(0x1234), 0x1234)
        self.assertEqual(uint16_conv.mb2py(0xfec6), 0xfec6)
        self.assertEqual(uint16_conv.mb2py([0x1234]), 0x1234)
        self.assertEqual(uint16_conv.mb2py([0xfec6]), 0xfec6)

    def test_int32LE(self):
        int32LE_conv = DataConverter("int32LE")
        self.assertEqual(int32LE_conv.str2mb( "0x12345678"), [0x1234, 0x5678])
        with self.assertRaises(struct.error):
            int32LE_conv.str2mb( "0xfedcba98")
        self.assertEqual(int32LE_conv.mb2py( [0x1234, 0x5678]), 0x12345678)
        self.assertEqual(int32LE_conv.mb2py( [0xF8A4, 0x6B57]), -123442345)

    def test_int32BE(self):
        int32BE_conv = DataConverter("int32BE")
        self.assertEqual(int32BE_conv.str2mb( "0x12345678"), [0x5678, 0x1234])
        with self.assertRaises(struct.error):
            int32BE_conv.str2mb( "0xfedcba98")
        self.assertEqual(int32BE_conv.mb2py( [0x1234, 0x5678]), 0x56781234)
        self.assertEqual(int32BE_conv.mb2py( [0x6B57, 0xF8A4]), -123442345)

    def test_uint32LE(self):
        uint32LE_conv = DataConverter("uint32LE")
        self.assertEqual(uint32LE_conv.str2mb( "0x12345678"), [0x1234, 0x5678])
        self.assertEqual(uint32LE_conv.str2mb( "0xfedcba98"), [0xfedc, 0xba98])
        with self.assertRaises(OverflowError):
            uint32LE_conv.str2mb( "-4095")
        self.assertEqual(uint32LE_conv.mb2py( [0x1234, 0x5678]), 0x12345678)
        self.assertEqual(uint32LE_conv.mb2py( [0xfedc, 0xba98]), 0xfedcba98)

    def test_uint32BE(self):
        uint32BE_conv = DataConverter("uint32BE")
        self.assertEqual(uint32BE_conv.str2mb( "0x12345678"), [0x5678, 0x1234])
        self.assertEqual(uint32BE_conv.str2mb( "0xfedcba98"), [0xba98, 0xfedc])
        self.assertEqual(uint32BE_conv.mb2py( [0x1234, 0x5678]), 0x56781234)
        self.assertEqual(uint32BE_conv.mb2py( [0xfedc, 0xba98]), 0xba98fedc)

    def test_float32LE(self):
        float32LE_conv = DataConverter("float32LE")
        self.assertEqual(float32LE_conv.str2mb( "3.1415926"), [0x4049, 0x0fda])
        self.assertEqual(float32LE_conv.str2mb( "-3.1415926"), [0xc049, 0x0fda])
        self.assertAlmostEqual(float32LE_conv.mb2py( [0x4049, 0x0fda]), 3.1415926, 6)
        self.assertAlmostEqual(float32LE_conv.mb2py( [0xc049, 0x0fda]), -3.1415926, 6)

    def test_float32BE(self):
        float32BE_conv = DataConverter("float32BE")
        self.assertEqual(float32BE_conv.str2mb( "3.1415926"), [0x0fda, 0x4049])
        self.assertEqual(float32BE_conv.str2mb( "-3.1415926"), [0x0fda, 0xc049])
        self.assertAlmostEqual(float32BE_conv.mb2py( [0x0fda, 0x4049]), 3.1415926, 6)
        self.assertAlmostEqual(float32BE_conv.mb2py( [0x0fda, 0xc049]), -3.1415926, 6)

    def test_stringLE(self):
        string10_conv = DataConverter("stringLE10")
        self.assertEqual(string10_conv.str2mb( "ShortStr"),   [0x6853, 0x726f, 0x5374, 0x7274, 0x0000])
        self.assertEqual(string10_conv.str2mb( "ExactLen90"), [0x7845, 0x6361, 0x4c74, 0x6e65, 0x3039])
        self.assertEqual(string10_conv.str2mb( "OddLenStr"),  [0x644f, 0x4c64, 0x6e65, 0x7453, 0x0072])        
        with self.assertRaises(ValueError):
            self.assertEqual(string10_conv.str2mb( "TooLongString"), [0x0000, 0x0000, 0x0000, 0x0000, 0x0000])
        self.assertEqual(string10_conv.mb2py( [0x6853, 0x726f, 0x5374, 0x7274, 0x0000]), 'ShortStr')
        self.assertEqual(string10_conv.mb2py( [0x7845, 0x6361, 0x4c74, 0x6e65, 0x3039]), 'ExactLen90')
        self.assertEqual(string10_conv.mb2py( [0x644f, 0x4c64, 0x6e65, 0x7453, 0x0072]), 'OddLenStr')

    def test_stringBE(self):
        string10_conv = DataConverter("stringBE10")
        self.assertEqual(string10_conv.str2mb( "ShortStr"),   [0x5368, 0x6f72, 0x7453, 0x7472, 0x0000])
        self.assertEqual(string10_conv.str2mb( "ExactLen90"), [0x4578, 0x6163, 0x744c, 0x656e, 0x3930])
        self.assertEqual(string10_conv.str2mb( "OddLenStr"),  [0x4f64, 0x644c, 0x656e, 0x5374, 0x7200])        
        with self.assertRaises(ValueError):
            self.assertEqual(string10_conv.str2mb( "TooLongString"), [0x0000, 0x0000, 0x0000, 0x0000, 0x0000])
        self.assertEqual(string10_conv.mb2py( [0x5368, 0x6f72, 0x7453, 0x7472, 0x0000]), 'ShortStr')
        self.assertEqual(string10_conv.mb2py( [0x4578, 0x6163, 0x744c, 0x656e, 0x3930]), 'ExactLen90')
        self.assertEqual(string10_conv.mb2py( [0x4f64, 0x644c, 0x656e, 0x5374, 0x7200]), 'OddLenStr')

    def test_list_bool(self):
        list_bool_conv = DataConverter("list-bool-5")
        self.assertEqual(list_bool_conv.str2mb("TRUE 1 off false on"), [1, 1, 0, 0, 1])
        self.assertEqual(list_bool_conv.mb2py([1, 1, 0, 0, 1]), "True True False False True")

    def test_list_int16(self):
        list_int16_conv = DataConverter("list-int16-5")
        self.assertEqual(list_int16_conv.str2mb("0x1234 -4095 1 12 123"), [0x1234, -4095, 1, 12, 123])
        self.assertEqual(list_int16_conv.mb2py([0x1234, 0xfec6, 0x0001, 0x0012, 0x0123]), "4660 -314 1 18 291")

    def test_list_uint16(self):
        list_uint16_conv = DataConverter("list-uint16-5")
        self.assertEqual(list_uint16_conv.str2mb( "0x1234 0x8000 0x4321 0x0192 0xffff"), [0x1234, 0x8000, 0x4321, 0x0192, 0xffff])
        self.assertEqual(list_uint16_conv.mb2py([0x1234, 0x8000, 0x4321, 0x0192, 0xffff]), "4660 32768 17185 402 65535")


if __name__ == '__main__':
    unittest.main()
