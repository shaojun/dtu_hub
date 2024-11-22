
import unittest
from parser import GPS_EBYTE_E108_D01_Parser
from models import SubDeviceRequest, REQUEST_TYPE

class TestGPS_EBYTE_E108_D01_Parser(unittest.TestCase):

    def setUp(self):
        self.parser = GPS_EBYTE_E108_D01_Parser()

    def test_serialize_read_request(self):
        request = SubDeviceRequest(request_type=REQUEST_TYPE.Read)
        expected_output = b'\x01\x03\x00\xC8\x00\x11\x04\x38'
        self.assertEqual(self.parser.Serialize(request), expected_output)

    def test_serialize_invalid_request(self):
        request = SubDeviceRequest(request_type="InvalidType")
        with self.assertRaises(ValueError):
            self.parser.Serialize(request)

    def test_check_raw_data_is_valid_device_response(self):
        valid_data = b'\x01\x03\x22\x00\x01\x07\xE8\x00\x0B\x00\x15\x00\x06\x00\x0F\x00\x08\x00\x45\x42\xF3\x28\x50\x00\x4E\x41\xF9\x3F\xAE\x00\x00\x00\x00\x43\x02\x70\xA4\x2A\x8C'
        self.assertTrue(self.parser.CheckRawDataIsValidDeviceResponse(valid_data))

        invalid_data = b'\x01\x03\x22\x00\x02\x07\xE8\x00\x0B\x00\x15\x00\x06\x00\x0F\x00\x08\x00\x45\x42\xF3\x28\x50\x00\x4E\x41\xF9\x3F\xAE\x00\x00\x00\x00\x43\x02\x70\xA4\x2A\x8C'
        self.assertFalse(self.parser.CheckRawDataIsValidDeviceResponse(invalid_data))

    def test_deserialize(self):
        data = b'\x01\x03\x22\x00\x01\x07\xE8\x00\x0B\x00\x15\x00\x06\x00\x0F\x00\x08\x00\x45\x42\xF3\x28\x50\x00\x4E\x41\xF9\x3F\xAE\x00\x00\x00\x00\x43\x02\x70\xA4\x2A\x8C'
        expected_output = {
            "year": 2024,
            "month": 11,
            "day": 21,
            "hour": 6,
            "min": 15,
            "sec": 8,
            "longitude": 1122861136,
            "latitude": 1107292078,
            "speed": 0,
            "heading": 1124076964
        }
        self.assertEqual(self.parser.Deserialize(data), expected_output)

if __name__ == '__main__':
    unittest.main()