import datetime
import time
import unittest
from unittest.mock import MagicMock, patch
import asyncio
import paho.mqtt.client as mqtt_client

from device.simple_mqtt_client import SimpleMqttClient


class TestSimpleMqttClient(unittest.TestCase):

    def setUp(self):
        self.mqtt_broker_url = "bs.shaojun.xyz"
        self.mqtt_client_id = "simple_mqtt_client"
        self.username = "test_user"
        self.password = "test_pass"
        self.sub_topic = "response_topic"
        self.log_func = lambda msg: print(f"{datetime.datetime.now()} - {msg}")
        self.client = SimpleMqttClient(
            self.mqtt_broker_url, self.mqtt_client_id, self.username, self.password, self.sub_topic,
            lambda client, msg: print(
                f"on_msg_received_callback-> {msg.payload.decode()}"), self.log_func)
        self.client.start_async()
        while not self.client.client.is_connected():
            print("Waiting for mqtt client to connect...")
            time.sleep(1)
        print("Connected to mqtt broker")

    # @patch.object(mqtt_client.Client, 'publish')
    # @patch.object(mqtt_client.Client, 'message_callback_add')
    # @patch.object(mqtt_client.Client, 'message_callback_remove')
    # @patch.object(mqtt_client.Client, 'is_connected', return_value=True)
    def test_send_async(self):
        async def run_test():
            request_topic = "request_topic"
            request_msg = "request_message"
            expected_response = "expected_response"

            def capture_response(raw_device_request_msg, raw_device_response_msg, context):
                return True

            # mock_publish.return_value = (0,)

            async def simulate_response(delay=1):
                await asyncio.sleep(delay)
                self.client.send(self.sub_topic, expected_response)

            asyncio.create_task(simulate_response())

            start_time = time.time()
            response = await self.client.send_async(request_topic, request_msg, self.sub_topic, capture_response, 4000)
            used_time_by_ms = (time.time() - start_time) * 1000
            self.assertIsNotNone(response, "The response should not be None")
            self.assertEqual(response.decode('utf-8'), expected_response)
            self.assertTrue(used_time_by_ms <= 1200 and used_time_by_ms >= 1000,
                            f"The used time should be less than 1200ms but actual: {used_time_by_ms}")

            asyncio.create_task(simulate_response(3))
            expected_response = "expected_response_2"
            start_time = time.time()
            response = await self.client.send_async(request_topic, request_msg, self.sub_topic, capture_response, 4000)
            used_time_by_ms = (time.time() - start_time) * 1000
            self.assertIsNotNone(response, "The response should not be None")
            self.assertEqual(response.decode('utf-8'), expected_response)
            self.assertTrue(used_time_by_ms <= 3200 and used_time_by_ms >= 3000,
                            f"The used time should be less than 1200ms but actual: {used_time_by_ms}")

        asyncio.run(run_test())


if __name__ == '__main__':
    unittest.main()
