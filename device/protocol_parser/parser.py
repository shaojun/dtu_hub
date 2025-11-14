import codecs
import logging
import struct
from typing import Union
from models import *
from abc import ABC, abstractmethod
from paho.mqtt.client import PayloadType


class DeviceProtocolParser(ABC):
    def __init__(self):
        self.max_keep_data_records_count = 300

    @abstractmethod
    def Serialize(self, request: DeviceRequest) -> PayloadType:
        pass

    @abstractmethod
    def TryParse(self, device_mqtt_msg_topic: str, device_mqtt_msg: PayloadType) -> tuple[Optional[DeviceIdentity], Optional[dict]]:
        pass

    # @abstractmethod
    # def Deserialize(self, raw_device_request_data: Union[bytes, str], raw_device_response_data: Union[bytes, str]) -> dict:
    #     pass

    def bcd_to_int(bcd_bytes: bytes):
        result = 0
        for byte in bcd_bytes:
            # Extract the high nibble and low nibble
            high_nibble = (byte >> 4) & 0xF
            low_nibble = byte & 0xF
            # Combine the nibbles into the result
            result = result * 100 + high_nibble * 10 + low_nibble
        return result


class GenericTimelyReportGpsDtuDeviceParser(DeviceProtocolParser):
    def __init__(self):
        super().__init__()
        self.logger = logging.getLogger("mqttClientLogger")
        self.max_keep_data_records_count = 100

    def Serialize(self, request: DeviceRequest) -> PayloadType:
        # this kind of dtu does not support actively query gps,
        # instead, it reports gps data as heartbeat msg actively with interval
        raise NotImplementedError("Serialize method not implemented")

    def TryParse(
            self,
            device_mqtt_msg_topic: str, device_mqtt_msg: PayloadType) -> tuple[Optional[DeviceIdentity], Optional[dict]]:
        if device_mqtt_msg is None:
            return None, None
        gnrmc_sentence: str = None
        if isinstance(device_mqtt_msg, bytes):
            try:
                gnrmc_sentence = device_mqtt_msg.decode()
            except UnicodeDecodeError:
                return None, None
        elif isinstance(device_mqtt_msg, str):
            gnrmc_sentence = device_mqtt_msg
        else:
            return None, None
        if not gnrmc_sentence.startswith("$GNRMC"):
            return None, None

        # 分割语句（去掉$开头和*后的校验码）
        parts = gnrmc_sentence.split('*')
        if len(parts) != 2:
            return None, None

        data_part, checksum_part = parts
        data_fields = data_part.split(',')

        # 修正：GNRMC标准字段数应为14个（包含$GNRMC本身），允许扩展字段
        # 核心字段需要前13个（索引0-12），扩展字段（定位模式、导航状态）在12+
        if len(data_fields) < 13:
            return None, None
        parsed_gnrmc = self.__parse_gnrmc(gnrmc_sentence)
        # Extract dtu_sn from topic
        dtu_sn = device_mqtt_msg_topic.split('/')[1]
        assert isinstance(dtu_sn, str)
        data_record = {"received_datetime": datetime.now(
            timezone.utc), "data": parsed_gnrmc}
        device_identity = DeviceIdentity(
            name=f"GenericTimelyReportGpsDtuDevice__{dtu_sn}",
            dtu_sn=dtu_sn,
            device_type=DEVICE_TYPE.DTU,
        )
        return device_identity, data_record

    def __parse_gnrmc(self, gnrmc_sentence: str) -> dict:
        """
        解析NMEA协议的$GNRMC语句，提取关键字段

        参数:
            gnrmc_sentence: GNRMC语句字符串（如$GNRMC,111700.00,A,2906.78084,N,11207.29890,E,0.114,,111125,,,A,V*10）

        返回:
            dict: 包含解析后的关键字段，格式如下：
            {
                "原始语句": str,
                "UTC时间": str (格式: HH:MM:SS.ss),
                "定位状态": str (A=有效定位, V=无效定位),
                "纬度": float (十进制度数),
                "纬度方向": str (N=北纬, S=南纬),
                "经度": float (十进制度数),
                "经度方向": str (E=东经, W=西经),
                "地面速度(节)": float,
                "地面航向(度)": str (空表示无数据),
                "UTC日期": str (格式: DD/MM/YY),
                "磁偏角(度)": str (空表示无数据),
                "磁偏角方向": str (E=东偏, W=西偏, 空表示无数据),
                "定位模式": str (A=自主定位, D=差分定位, E=估算, N=数据无效),
                "导航状态": str (V=未定位, A=定位, 部分模块扩展字段),
                "校验状态": str (OK=校验通过, ERROR=校验失败)
            }

        异常:
            ValueError: 当输入不是有效的GNRMC语句时抛出
        """
        # 基础校验
        if not gnrmc_sentence.startswith("$GNRMC"):
            raise ValueError("输入不是有效的GNRMC语句")

        # 分割语句（去掉$开头和*后的校验码）
        parts = gnrmc_sentence.split('*')
        if len(parts) != 2:
            raise ValueError("GNRMC语句格式错误，缺少校验码")

        data_part, checksum_part = parts
        data_fields = data_part.split(',')

        # 修正：GNRMC标准字段数应为14个（包含$GNRMC本身），允许扩展字段
        # 核心字段需要前13个（索引0-12），扩展字段（定位模式、导航状态）在12+
        if len(data_fields) < 13:
            raise ValueError(
                f"GNRMC语句字段不完整，期望至少13个核心字段，实际收到{len(data_fields)}个")

        # 计算校验和并验证（NMEA校验规则：所有字段的异或运算）
        def calculate_nmea_checksum(sentence: str) -> str:
            """计算NMEA语句的校验和（去掉$和*后的部分）"""
            checksum = 0
            for char in sentence[1:]:  # 跳过开头的$
                if char == '*':
                    break
                checksum ^= ord(char)
            return f"{checksum:02X}"  # 转为两位十六进制字符串

        expected_checksum = calculate_nmea_checksum(gnrmc_sentence)
        checksum_valid = expected_checksum == checksum_part.upper()

        # 解析核心字段
        # 1. UTC时间（格式：HHMMSS.ss）
        utc_time_raw = data_fields[1]
        utc_time = f"{utc_time_raw[:2]}:{utc_time_raw[2:4]}:{utc_time_raw[4:]}" if utc_time_raw else "无数据"

        # 2. 定位状态
        status = "有效定位" if data_fields[2] == 'A' else "无效定位" if data_fields[
            2] == 'V' else f"未知({data_fields[2]})"

        # 3. 纬度（NMEA格式：DDMM.MMMMM -> 十进制：DD + MM.MMMMM/60）
        latitude_raw = data_fields[3]
        latitude_dir = data_fields[4] if data_fields[4] in ['N', 'S'] else "未知"
        latitude = 0.0
        if latitude_raw:
            degrees = int(latitude_raw[:2])
            minutes = float(latitude_raw[2:])
            latitude = degrees + minutes / 60.0
            # 南纬为负值
            if latitude_dir == 'S':
                latitude = -latitude

        # 4. 经度（NMEA格式：DDDMM.MMMMM -> 十进制：DDD + MM.MMMMM/60）
        longitude_raw = data_fields[5]
        longitude_dir = data_fields[6] if data_fields[6] in [
            'E', 'W'] else "未知"
        longitude = 0.0
        if longitude_raw:
            degrees = int(longitude_raw[:3])
            minutes = float(longitude_raw[3:])
            longitude = degrees + minutes / 60.0
            # 西经为负值
            if longitude_dir == 'W':
                longitude = -longitude

        # 5. 地面速度（节，1节=1.852公里/小时）
        speed_knots = float(data_fields[7]) if data_fields[7] else 0.0

        # 6. 地面航向
        course = data_fields[8] if data_fields[8] else "无数据"

        # 7. UTC日期（格式：DDMMYY -> 转换为DD/MM/YY）
        date_raw = data_fields[9]
        utc_date = f"{date_raw[:2]}/{date_raw[2:4]}/{date_raw[4:]}" if date_raw else "无数据"

        # 8. 磁偏角
        magnetic_variation = data_fields[10] if data_fields[10] else "无数据"
        magnetic_dir = data_fields[11] if data_fields[11] in [
            'E', 'W'] else "无数据"

        # 9. 定位模式（NMEA 2.3+扩展字段，索引12）
        mode = {
            'A': '自主定位',
            'D': '差分定位',
            'E': '估算定位',
            'N': '数据无效'
        }.get(data_fields[12], f"未知({data_fields[12]})") if len(data_fields) > 12 and data_fields[12] else "无数据"

        # 10. 导航状态（部分模块扩展字段，索引13）
        nav_status = {
            'A': '定位',
            'V': '未定位'
        }.get(data_fields[13], f"未知({data_fields[13]})") if len(data_fields) > 13 and data_fields[13] else "无数据"

        # 组织返回结果
        return {
            "原始语句": gnrmc_sentence,
            "UTC时间": utc_time,
            "定位状态": status,
            "纬度": round(latitude, 6),  # 保留6位小数（约10cm精度）
            "纬度方向": latitude_dir,
            "经度": round(longitude, 6),
            "经度方向": longitude_dir,
            "地面速度(节)": round(speed_knots, 3),
            "地面速度(km/h)": round(speed_knots * 1.852, 3),  # 额外转换为公里/小时
            "地面航向(度)": course,
            "UTC日期": utc_date,
            "磁偏角(度)": magnetic_variation,
            "磁偏角方向": magnetic_dir,
            "定位模式": mode,
            "导航状态": nav_status,
            "校验状态": "OK" if checksum_valid else "ERROR"}


class Probe_YiTong_TankTruck_Parser(DeviceProtocolParser):
    def __init__(self):
        super().__init__()
        self.logger = logging.getLogger("mqttClientLogger")
        self.max_keep_data_records_count = 100

    def Serialize(self, request: DeviceRequest) -> Union[bytes, str]:
        """
        接收命令格式为： AA 类别号 探棒号 命令 参数 校验和 BB
            例： AA   01     01    06   00    08   BB
        命令仅有1条（取数），类别号为01，探棒号1-99，命令为06，参数 00
        探棒号为1字节BCD码
        校验和为前4字节十进制加和。

        """
        # Implement serialization logic for Probe_YiTong_TankTruck
        if request.request_action == REQUEST_ACTION.Read:
            msg = b'\xAA\x01'
            msg += struct.pack('B', int(request.device_identity.device_physical_id))
            msg += b'\x06\x00'
            checksum = sum(msg[1:5])
            msg += struct.pack('B', checksum)
            msg += b'\xBB'
            return msg
        raise ValueError("Unsupported request type")

    def TryParse(
            self,
            device_mqtt_msg_topic: str, device_mqtt_msg: PayloadType) -> tuple[Optional[DeviceIdentity], Optional[dict]]:
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
        if not isinstance(device_mqtt_msg, bytes):
            return None, None
        debug_hex_str = codecs.encode(
            device_mqtt_msg, 'hex').decode('utf-8')
        if len(device_mqtt_msg) != (1+13+2*device_mqtt_msg[13]+2+1+1):
            return None, None
        body: bytes = device_mqtt_msg[1:-1]

        # check the 类别号
        if body[0] != 0x01:
            return None, None
        # check the 探棒号 should the same with the request
        probe_physical_id = body[1]
        # check the 探棒类型 should be 0x02
        if body[2] != 0x02:
            return None, None
        # check the 校验和
        # debug_hex_str = codecs.encode(
        #     raw_device_response_data[1:-2], 'hex').decode('utf-8')
        # print(
        #     f"Probe_YiTong_TankTruck_Parser, CheckIsRequestAndResponsePair: {debug_hex_str}")
        # checksum = sum(raw_device_response_data[1:-2]) & 0x00FF
        # if checksum != raw_device_response_data[-2]:
        #     return existing_device, TryUpdateOrCreateDeviceResult.NotMatched
        # Extract dtu_sn from topic
        dtu_sn = device_mqtt_msg_topic.split('/')[1]
        assert isinstance(dtu_sn, str)
        parsed_data = self.__parse_probe_reading_data(body)
        data_record = {"received_datetime": datetime.now(
            timezone.utc), "data": parsed_data}
        device_intity = DeviceIdentity(
            name=f"Probe_YiTong_TankTruck__{dtu_sn}__{body[1]:02d}",
            dtu_sn=dtu_sn,
            device_type=DEVICE_TYPE.SUB_DEVICE__Probe_YiTong_TankTruck,
            device_physical_id=str(probe_physical_id),
        )
        return device_intity, data_record

    def __parse_probe_reading_data(self, raw_data: bytes) -> dict:
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
        if not isinstance(raw_data, bytes):
            raise ValueError("Invalid data type, must be bytes")
        parsed_data = {}
        body: bytes = raw_data
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
