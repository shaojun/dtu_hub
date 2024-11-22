import codecs
import struct
from typing import Union
from models import *
from abc import ABC, abstractmethod


class DeviceProtocolParser(ABC):
    @abstractmethod
    def Serialize(self, request: SubDeviceRequest) -> Union[bytes, str]:
        pass

    @abstractmethod
    def CheckRawDataIsValidDeviceResponse(self, raw_device_request_data: Union[bytes, str], raw_device_response_data: bytes, context: dict) -> bool:
        pass

    @abstractmethod
    def Deserialize(self, data: Union[bytes, str]) -> dict:
        pass

    def bcd_to_int(bcd_bytes: bytes):
        result = 0
        for byte in bcd_bytes:
            # Extract the high nibble and low nibble
            high_nibble = (byte >> 4) & 0xF
            low_nibble = byte & 0xF
            # Combine the nibbles into the result
            result = result * 100 + high_nibble * 10 + low_nibble
        return result


class GPS_EBYTE_E108_D01_Parser(DeviceProtocolParser):
    def Serialize(self, request: SubDeviceRequest) -> Union[bytes, str]:
        # Implement serialization logic for GPS_EBYTE_E108_D01
        """
        from doc, sending: 01(设备地址)03(功能码)00C8(寄存器首地址)0011(读取数量)0438(Modbus CRC校验)
        """
        if request.request_type == REQUEST_TYPE.Read:
            # return the bytes of 010300C800110438
            return b'\x01\x03\x00\xC8\x00\x11\x04\x38'
        raise ValueError("Unsupported request type")

    def CheckRawDataIsValidDeviceResponse(
            self,
            raw_device_request_data: Union[bytes, str],
            raw_device_response_data: bytes,
            context: dict) -> bool:
        """
        from doc, receiving:
        01(设备地址) 03(功能码) 22(data len)  
        00 01(定位有效性)
        07 E8(year)  00 0B(month)  00 15(day) 00 06(hour) 00 0F(min) 00 08(sec) 
        00 45(经度方向,低位有效,HEX to ASCII, E(东经))  42 F3 28 50(经度,32位浮点数,大端-大端) 
        00 4E(纬度方向,低位有效,HEX to ASCII, N(北纬))  41 F9 3F AE(纬度,32位浮点数,大端-大端) 
        00 00 00 00(对地速度,32位浮点数,大端-大端)  
        43 02 70 A4(对地航向,32位浮点数,大端-大端)
        2A 8C(Modbus CRC校验)         
        """
        if not isinstance(raw_device_response_data, bytes):
            return False
        if len(raw_device_response_data) != (3+raw_device_response_data[2]+2):
            return False
        try:
            body: bytes = raw_device_response_data[3:-2]
            # print(codecs.encode(body, 'hex'))
            # check first 2 bytes, must be 0x0000 or 0x0001
            if body[0] != 0x00 or body[1] not in [0x00, 0x01]:
                return False
            # check the year, month, day, hour, min, sec are valid
            year = int.from_bytes(body[2:4], byteorder='big')
            # are we still alive at year 2050?
            if year < 2024 or year > 2050:
                return False
            return True
        except Exception as e:
            print(f"CheckRawDataIsValidDeviceResponse error: {e}")
            return False

    def Deserialize(self, data: Union[bytes, str]) -> dict:
        # Implement deserialization logic for GPS_EBYTE_E108_D01
        """
        from doc, receiving:
        01(设备地址) 03(功能码) 22(data len)  
        00 01(定位有效性)
        07 E8(year 2024)  00 0B(month 11)  00 15(day 21) 00 06(hour 6) 00 0F(min 15) 00 08(sec 8) 
        00 45(经度方向,低位有效,HEX to ASCII, E(东经))  42 F3 28 73(经度,32位浮点数,大端-大端,121.579) 
        00 4E(纬度方向,低位有效,HEX to ASCII, N(北纬))  41 F9 3F 8F(纬度,32位浮点数,大端-大端,31.156034) 
        00 00 00 00(对地速度,32位浮点数,大端-大端)  
        43 02 70 A4(对地航向,32位浮点数,大端-大端)
        2A 8C(Modbus CRC校验)         
        """
        if not isinstance(data, bytes):
            raise ValueError("Invalid data type, must be bytes")
        body: bytes = data[3:-2]
        is_location_valid = body[1] == 0x01
        year = int.from_bytes(body[2:4], byteorder='big')
        month = int.from_bytes(body[4:6], byteorder='big')
        day = int.from_bytes(body[6:8], byteorder='big')
        hour = int.from_bytes(body[8:10], byteorder='big')
        min = int.from_bytes(body[10:12], byteorder='big')
        sec = int.from_bytes(body[12:14], byteorder='big')

        longitude_heading_raw = body[14:16]
        longitude_heading = chr(longitude_heading_raw[1])
        longitude = struct.unpack('>f', body[16:20])[0]
        latitude_heading_raw = body[20:22]
        latitude_heading = chr(latitude_heading_raw[1])
        latitude = struct.unpack('>f', body[22:26])[0]

        speed_to_ground = struct.unpack('>f', body[26:30])[0]
        heading_to_ground = struct.unpack('>f', body[30:34])[0]
        return {
            "is_location_valid": is_location_valid,
            "year": year,
            "month": month,
            "day": day,
            "hour": hour,
            "min": min,
            "sec": sec,
            "longitude_heading": longitude_heading,
            "longitude": longitude,
            "latitude_heading": latitude_heading,
            "latitude": latitude,
            "speed_to_ground": speed_to_ground,
            "heading_to_ground": heading_to_ground
        }


class Probe_YiTong_TankTruck_Parser(DeviceProtocolParser):
    def Serialize(self, request: SubDeviceRequest) -> Union[bytes, str]:
        """
        接收命令格式为： AA 类别号 探棒号 命令 参数 校验和 BB
            例： AA   01     01    06   00    08   BB
        命令仅有1条（取数），类别号为01，探棒号1-99，命令为06，参数 00
        探棒号为1字节BCD码
        校验和为前4字节十进制加和。

        """
        # Implement serialization logic for Probe_YiTong_TankTruck
        if request.request_type == REQUEST_TYPE.Read:
            msg = b'\xAA\x01'
            msg += struct.pack('B', int(request.physical_id))
            msg += b'\x06\x00'
            checksum = sum(msg[1:5])
            msg += struct.pack('B', checksum)
            msg += b'\xBB'
            return msg
        raise ValueError("Unsupported request type")

    def CheckRawDataIsValidDeviceResponse(self, raw_device_request_data: Union[bytes, str], raw_device_response_data: bytes, context: dict) -> bool:
        """
        返回数据格式：
        AA 数据 校验和 BB     （数据字节数 = 13+2×温度点数）
        数据定义：（所有数据均为压缩BCD码,一字节表示2位十进制数）
        字节序号	内容	字节数	说明
        0	类别号	1	固定为 01
        1	探棒号	1	
        2	探棒类型	1	固定为02
        3-5	M1	3	液面浮子到电子仓的长度，6位十进制整数，BCD码
        6-8	M2	3	返回6位9
        9-11	M3	3	备用
        12	温度点数	02	探棒中安装的温度传感器个数
        13-14	温度A	2	温度加80的值,3位整数，1位小数，探杆的中间位置温度
        15-16	温度B	2	温度加80的值,3位整数，1位小数，探杆的尾部位置温度
        17-18		2	备用
        校验和为所有数据十进制加和，取低字节。
        探棒类型 02 输出空高
        M1  液面浮子到电子仓的长度。
        举例：探棒收到命令  AA 01 01 06 00 08 BB
        探棒返回数据  AA 01 01 02 03 21 37 99 99 99 00 25 01 02 10 67 10 49 99 99 87 BB
        分析数据如下：
        AA 开始符01类别号01探棒号02探棒类型
        03 21 37液面浮子到电子仓的长度321.37mm
        99 99 99 这3字节备用
        00 25 01 这3字节备用
        02  标示2个温度点
        10 67 探杆中间温度 26.7℃
        10 49 探杆尾部温度24.9℃
        99 99 这2字节备用 
        87 校验和 
        BB结束符。

        """
        if not isinstance(raw_device_response_data, bytes):
            return False
        if len(raw_device_response_data) != (13+2*raw_device_response_data[12]+2):
            return False
        try:
            body: bytes = raw_device_response_data[1:-1]
            # check the 类别号
            if body[0] != 0x01:
                return False
            # check the 探棒号 should the same with the request
            if body[1] != int(raw_device_request_data[2]):
                return False
            # check the 探棒类型 should be 0x02
            if body[2] != 0x02:
                return False
            # check the 校验和
            checksum = sum(body) & 0xFF
            if checksum != raw_device_response_data[-2]:
                return False
            return True
        except Exception as e:
            print(f"CheckRawDataIsValidDeviceResponse error: {e}")
            return False

    def Deserialize(self, data: Union[bytes, str]) -> dict:
        """
        返回数据格式：
        AA 数据 校验和 BB     （数据字节数 = 13+2×温度点数）
        数据定义：（所有数据均为压缩BCD码,一字节表示2位十进制数）
        字节序号	内容	字节数	说明
        0	类别号	1	固定为 01
        1	探棒号	1	
        2	探棒类型	1	固定为02
        3-5	M1	3	液面浮子到电子仓的长度，6位十进制整数，BCD码
        6-8	M2	3	返回6位9
        9-11	M3	3	备用
        12	温度点数	02	探棒中安装的温度传感器个数
        13-14	温度A	2	温度加80的值,3位整数，1位小数，探杆的中间位置温度
        15-16	温度B	2	温度加80的值,3位整数，1位小数，探杆的尾部位置温度
        17-18		2	备用
        校验和为所有数据十进制加和，取低字节。
        探棒类型 02 输出空高
        M1  液面浮子到电子仓的长度。
        举例：探棒收到命令  AA 01 01 06 00 08 BB
        探棒返回数据  AA 01 01 02 03 21 37 99 99 99 00 25 01 02 10 67 10 49 99 99 87 BB
        分析数据如下：
        AA 开始符01类别号01探棒号02探棒类型
        03 21 37液面浮子到电子仓的长度321.37mm
        99 99 99 这3字节备用
        00 25 01 这3字节备用
        02  标示2个温度点
        10 67 探杆中间温度 26.7℃
        10 49 探杆尾部温度24.9℃
        99 99 这2字节备用 
        87 校验和 
        BB结束符。

        """
        # Implement deserialization logic for Probe_YiTong_TankTruck
        if not isinstance(data, bytes):
            raise ValueError("Invalid data type, must be bytes")
        parsed_data = {}
        body: bytes = data[1:-1]
        # check the 类别号
        类别号 = body[0]
        # check the 探棒号
        探棒号 = body[1]
        # check the 探棒类型
        探棒类型 = body[2]
        # check the M1, 6位十进制整数，BCD码
        M1 = DeviceProtocolParser.bcd_to_int(body[3:6])
        # check the M2
        M2 = DeviceProtocolParser.bcd_to_int(body[6:9])
        # check the M3
        M3 = int.from_bytes(body[9:12], byteorder='big')
        # check the 温度点数
        温度点数 = DeviceProtocolParser.bcd_to_int(body[12:13])
        parsed_data = {
            "类别号": 类别号,
            "探棒号": 探棒号,
            "探棒类型": 探棒类型,
            "M1": M1,
            "M2": M2,
            "M3": M3,
            "温度点数": 温度点数,
            "温度": []
        }
        for i in range(温度点数):
            温度A = DeviceProtocolParser.bcd_to_int(body[13:15])/10-80
            温度B = DeviceProtocolParser.bcd_to_int(body[15:17])/10-80
            parsed_data["温度"].append({"温度A": 温度A, "温度B": 温度B})
        return parsed_data
