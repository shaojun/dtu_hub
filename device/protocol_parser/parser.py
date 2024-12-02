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
    def CheckIsRequestAndResponsePair(self, raw_device_request_data: Union[bytes, str], raw_device_response_data: bytes, context: dict) -> bool:
        pass

    @abstractmethod
    def Deserialize(self, raw_device_request_data: Union[bytes, str], raw_device_response_data: Union[bytes, str]) -> dict:
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
    def get_crc16(self, data: bytes) -> bytes:
        """
        @param data: bytes, the data to calculate the CRC16, from 设备地址 到 读取数量
        """
        crc = 0xFFFF
        for byte in data:
            crc ^= byte
            for _ in range(8):
                if crc & 0x0001:
                    crc >>= 1
                    crc ^= 0xA001
                else:
                    crc >>= 1
        return crc.to_bytes(2, byteorder='little')

    def Serialize(self, request: SubDeviceRequest) -> Union[bytes, str]:
        # Implement serialization logic for GPS_EBYTE_E108_D01
        """
        @return: bytes of msg, in structure of: device_address_byte + msg_body + crc, 
        sample 1, 读取定位数据: 01 0300050023 1412, 
        sample 2: 读取设备波特率: 01 0300030001 740A,
        sample 3, 修改波特率: 01 0600030003 39CB
        """
        # convert the physical_id to bytes
        device_address_byte = struct.pack('B', int(request.physical_id))
        if request.request_type == REQUEST_TYPE.Read:
            msg_body = b'\x03\x00\xC8\x00\x11'
            crc = self.get_crc16(device_address_byte + msg_body)
            return device_address_byte + msg_body + crc
        elif request.request_type == REQUEST_TYPE.Read_Advanced:
            # interpret the Read_Advanced to 读取设备波特率
            """
            request raw data sample: 01 0300030001 740A
            """
            msg_body = b'\x03\x00\x03\x00\x01'
            crc = self.get_crc16(device_address_byte + msg_body)
            return device_address_byte + msg_body + crc

        elif request.request_type == REQUEST_TYPE.Write:
            # interpret the Write to modify the baud rate to 2400bps
            """
            request raw data sample: 01060003000339CB, the CRC校验 are 39 and CB

            寄存器功能      寄存器地址        数据格式      数据范围/备注
            波特率          0003             Int16        波特率代码：
                                                            0x0000：1200bps，0x0001：2400bps，
                                                            0x0002：4800bps，0x0003：9600bps，
                                                            0x0004：19200bps，0x0005：38400bps，
                                                            0x0006：57600bps，0x0007：115200bps，
            """
            msg_body = b'\x06\x00\x03\x00\x01'
            crc = self.get_crc16(device_address_byte + msg_body)
            return device_address_byte + msg_body + crc
        elif request.request_type == REQUEST_TYPE.ReWrite:
            # interpret the ReWrite to modify the baud rate to 9600bps
            # 修改波特率 sample: 01 0600030003 39CB
            msg_body = b'\x06\x00\x03\x00\x03'
            crc = self.get_crc16(device_address_byte + msg_body)
            return device_address_byte + msg_body + crc
        raise ValueError("Unsupported request type")

    def CheckIsRequestAndResponsePair(
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
            # 读取定位数据 request sample: 01 0300050023 1412 or 01 0300c80011 0438
            if raw_device_request_data[1] == 0x03 and (raw_device_request_data[3] == 0x05 or raw_device_request_data[3] == 0xC8):
                body: bytes = raw_device_response_data[3:-2]
                # print(codecs.encode(body, 'hex'))
                # check first 2 bytes, must be 0x0000 or 0x0001
                if body[0] != 0x00 or body[1] not in [0x00, 0x01]:
                    return False
                # check the year, month, day, hour, min, sec are valid
                year = int.from_bytes(body[2:4], byteorder='big')
                # are we still alive?
                if year < 1999 or year > 2150:
                    return False
            # 读取设备波特率 request sample: 01 0300030001 740A, response sample: 01 03020003 F845
            elif raw_device_request_data[1] == 0x03 and raw_device_request_data[2] == 0x00 and raw_device_request_data[3] == 0x03:
                # check the baud rate is 0x0001 to 0x0007
                if raw_device_response_data[3] != 0x00 or raw_device_response_data[4] not in [0x00, 0x01, 0x02, 0x03, 0x04, 0x05, 0x06, 0x07]:
                    return False
            # 修改波特率 request sample: 01 0600030003 39CB, response sample: 01 0600030003 39CB
            elif raw_device_request_data[1] == 0x06 and raw_device_request_data[2] == 0x00 and raw_device_request_data[3] == 0x03:
                # check the baud rate is 0x0003
                if raw_device_response_data[1] != 0x06 or raw_device_response_data[4] != 0x00 or raw_device_response_data[5] not in [0x00, 0x01, 0x02, 0x03, 0x04, 0x05, 0x06, 0x07]:
                    return False
            return True
        except Exception as e:
            print(f"CheckRawDataIsValidDeviceResponse error: {e}")
            return False

    def Deserialize(self, raw_device_request_data: Union[bytes, str], raw_device_response_data: Union[bytes, str]) -> dict:
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
        if not isinstance(raw_device_response_data, bytes):
            raise ValueError("Invalid data type, must be bytes")
        # 读取定位数据 request sample: 01 0300050023 1412 or 01 0300c80011 0438
        if raw_device_request_data[1] == 0x03 and (raw_device_request_data[3] == 0x05 or raw_device_request_data[3] == 0xC8)\
                and raw_device_response_data[1] == 0x03:
            body: bytes = raw_device_response_data[3:-2]
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
        # 读取设备波特率 request sample: 010300030001740A, response sample:0103020003F845
        elif raw_device_request_data[1] == 0x03 and raw_device_request_data[3] == 0x03 and\
                raw_device_response_data[1] == 0x03 and raw_device_response_data[2] == 0x02:
            baud_rate_raw = raw_device_response_data[4]
            baud_rate_readable = [1200, 2400, 4800, 9600,
                                  19200, 38400, 57600, 115200][baud_rate_raw]
            return {
                "baud_rate": baud_rate_readable
            }

        # 修改波特率 request sample: 01060003000339CB,  response sample: 01 0600030003 39CB
        elif raw_device_request_data[1] == 0x03 and raw_device_request_data[3] == 0x03 and\
                raw_device_response_data[1] == 0x06 and raw_device_response_data[2] == 0x00 and raw_device_response_data[3] == 0x03:
            baud_rate_raw = raw_device_response_data[4]
            baud_rate_readable = [1200, 2400, 4800, 9600,
                                  19200, 38400, 57600, 115200][baud_rate_raw]
            """
            波特率代码：
            0x0000：1200bps，0x0001：2400bps，
            0x0002：4800bps，0x0003：9600bps，
            0x0004：19200bps，0x0005：38400bps，
            0x0006：57600bps，0x0007：115200bps
            """
            baud_rate_readable = [1200, 2400, 4800, 9600,
                                  19200, 38400, 57600, 115200][baud_rate_raw]
            return {
                "baud_rate": baud_rate_readable
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

    def CheckIsRequestAndResponsePair(self, raw_device_request_data: Union[bytes, str], raw_device_response_data: bytes, context: dict) -> bool:
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
        分析数据如下：aa 01 01 02 01 79 58 99 99 99 00 11 47 02 09 96 09 91 09 99 12 bb
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
        debug_hex_str = codecs.encode(
            raw_device_response_data, 'hex').decode('utf-8')
        print(
            f"Probe_YiTong_TankTruck_Parser, CheckIsRequestAndResponsePair: {debug_hex_str}")
        if len(raw_device_response_data) != (1+13+2*raw_device_response_data[13]+2+1+1):
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
            # debug_hex_str = codecs.encode(
            #     raw_device_response_data[1:-2], 'hex').decode('utf-8')
            # print(
            #     f"Probe_YiTong_TankTruck_Parser, CheckIsRequestAndResponsePair: {debug_hex_str}")
            # checksum = sum(raw_device_response_data[1:-2]) & 0x00FF
            # if checksum != raw_device_response_data[-2]:
            #     return False
            return True
        except Exception as e:
            print(f"CheckRawDataIsValidDeviceResponse error: {e}")
            return False

    def Deserialize(self, raw_device_request_data: Union[bytes, str], raw_device_response_data: Union[bytes, str]) -> dict:
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
        if not isinstance(raw_device_response_data, bytes):
            raise ValueError("Invalid data type, must be bytes")
        parsed_data = {}
        body: bytes = raw_device_response_data[1:-1]
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

        if 温度点数 == 0:
            raise ValueError("No temperature data as 温度点数 is 0")
        elif 温度点数 == 1:
            温度A = DeviceProtocolParser.bcd_to_int(body[13:15])/10-80
            parsed_data["温度"].append({"温度A": 温度A})
        elif 温度点数 == 2:
            温度A = DeviceProtocolParser.bcd_to_int(body[13:15])/10-80
            温度B = DeviceProtocolParser.bcd_to_int(body[15:17])/10-80
            parsed_data["温度"].append({"温度A": 温度A, "温度B": 温度B})
        return parsed_data
