from logging import Logger
import time
import uuid
from device.simple_mqtt_client import SimpleMqttClient
from models import *
from device.protocol_parser.parser import DeviceProtocolParser
import inspect
import paho.mqtt.client as mqtt_client


class DeviceCommunicator:
    def __init__(self, logger: Logger):
        self.logger = logger
        self.simple_mqtt_client: SimpleMqttClient = None
        self.protocol_parsers: list[DeviceProtocolParser] = self._initialize_protocol_parsers(
        )

    def _initialize_protocol_parsers(self) -> list[DeviceProtocolParser]:
        parser_classes = [
            cls for _, cls in inspect.getmembers(
                __import__('device.protocol_parser.parser', fromlist=['']),
                lambda member: inspect.isclass(member) and issubclass(
                    member, DeviceProtocolParser) and member is not DeviceProtocolParser
            )
        ]
        return [parser_class() for parser_class in parser_classes]

    def __init_mqtt_client__(self):
        mqtt_broker_url = "bs.shaojun.xyz"
        mqtt_client_id = f"dtu_hub_simple_mqtt_client_{uuid.getnode()}"
        username = "test_user"
        password = "test_pass"
        sub_topic = ["dtu/+/outbox"]

        def log_func(msg):
            self.logger.debug(msg)

        def bulk_logger(client, msg: mqtt_client.MQTTMessage):
            self.logger.debug(
                f"topic: {msg.topic} - payload: {msg.payload.decode()}")
        self.simple_mqtt_client = SimpleMqttClient(
            mqtt_broker_url, mqtt_client_id, username, password, sub_topic,
            bulk_logger, log_func)
        self.simple_mqtt_client.start_async()
        while not self.simple_mqtt_client.client.is_connected():
            print("Waiting for mqtt client to connect...")
            self.logger.info("Waiting for mqtt client to connect...")
            time.sleep(1)
        print("Connected to mqtt broker")
        self.logger.info("Connected to mqtt broker")

    def init(self):
        self.__init_mqtt_client__()

    async def send_async(self, request: SubDeviceRequest, timeout_ms: int) -> SubDeviceResponse:
        parser = next(
            (parser for parser in self.protocol_parsers if request.device_type in parser.__class__.__name__), None)
        if parser is None:
            raise ValueError(f"Unsupported device type: {request.type}")
        device_request_data = parser.Serialize(request)
        response_device_raw_data = await self.simple_mqtt_client.send_async(
            f"dtu/{request.dtu_sn}/inbox",
            device_request_data,
            None,
            lambda device_raw_req_msg, device_raw_resp_msg, context: parser.CheckIsRequestAndResponsePair(
                device_raw_req_msg, device_raw_resp_msg, context),
            timeout_ms)
        if response_device_raw_data is None:
            return SubDeviceResponse(
                id=request.id,
                dtu_sn=request.dtu_sn,
                physical_id=request.physical_id,
                device_type=request.device_type,
                request_type=request.request_type,
                overall_state_code=400, description="Timeout to receive response from device"
            )
        response_data = parser.Deserialize(
            device_request_data, response_device_raw_data)
        return SubDeviceResponse(
            id=request.id,
            dtu_sn=request.dtu_sn,
            physical_id=request.physical_id,
            device_type=request.device_type,
            request_type=request.request_type,
            data=response_data
        )
