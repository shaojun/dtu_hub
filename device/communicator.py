# from logging import Logger
# import logging
# import time
# from typing import Callable
# import uuid
# from device.simple_mqtt_client import SimpleMqttClient
# from models import *
# from device.protocol_parser.parser import DeviceProtocolParser
# import inspect
# import paho.mqtt.client as mqtt_client


# class DeviceCommunicator:
#     def __init__(self):
#         self.logger = logging.getLogger("communicatorLogger")
#         self.simple_mqtt_client: SimpleMqttClient = None
#         self.protocol_parsers: list[DeviceProtocolParser] = self._initialize_protocol_parsers(
#         )

#         mqtt_broker_url = "daefcc-cloud.top"
#         mqtt_client_id = f"dtu_hub_simple_mqtt_client_{uuid.getnode()}"
#         username = "test_user"
#         password = "test_pass"
#         # sub_topic = ["dtu/+/outbox"]

#         # def bulk_logger(client, msg: mqtt_client.MQTTMessage):
#         #     pass
#         self.simple_mqtt_client = SimpleMqttClient(
#             host=mqtt_broker_url,
#             port=1883,
#             name="SimpleMqttClient",
#             mqtt_client_id=mqtt_client_id,
#             username=username,
#             password=password,
#             on_message_callback=None,
#             logger=self.logger,
#             description="DTU Hub Simple MQTT Client",
#         )

#     def _initialize_protocol_parsers(self) -> list[DeviceProtocolParser]:
#         parser_classes = [
#             cls for _, cls in inspect.getmembers(
#                 __import__('device.protocol_parser.parser', fromlist=['']),
#                 lambda member: inspect.isclass(member) and issubclass(
#                     member, DeviceProtocolParser) and member is not DeviceProtocolParser
#             )
#         ]
#         return [parser_class() for parser_class in parser_classes]

#     def start(self):
#         self.simple_mqtt_client.connect()

#     def send_request(self, request: DeviceRequest, timeout_ms: int) -> SubDeviceResponse:
#         parser = next(
#             (parser for parser in self.protocol_parsers if request.device_type in parser.__class__.__name__), None)
#         if parser is None:
#             raise ValueError(f"Unsupported device type: {request.type}")
#         device_request_data = parser.Serialize(request)
#         response_device_raw_data = self.simple_mqtt_client.send_request(
#             f"dtu/{request.dtu_sn}/inbox",
#             f"dtu/{request.dtu_sn}/outbox",
#             device_request_data,
#             lambda device_raw_req_msg, device_raw_resp_msg, context: parser.TryParse(
#                 device_raw_req_msg, device_raw_resp_msg, context),
#             timeout_ms)
#         if response_device_raw_data is None:
#             return SubDeviceResponse(
#                 id=request.id,
#                 dtu_sn=request.dtu_sn,
#                 physical_id=request.physical_id,
#                 device_type=request.device_type,
#                 request_type=request.request_action,
#                 overall_state_code=400, description="Timeout to receive response from device"
#             )
#         response_data = parser.Deserialize(
#             device_request_data, response_device_raw_data)
#         return SubDeviceResponse(
#             id=request.id,
#             dtu_sn=request.dtu_sn,
#             physical_id=request.physical_id,
#             device_type=request.device_type,
#             request_type=request.request_action,
#             data=response_data
#         )
