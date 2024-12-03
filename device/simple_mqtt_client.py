import datetime
import json
import os
import time
from typing import Callable, Union
import paho.mqtt.client as mqtt_client
import asyncio
import threading


class SimpleMqttClient:
    def __init__(self, mqtt_broker_url, mqtt_client_id,
                 username, password,
                 sub_topics: Union[str, list[str]],
                 on_msg_received_callback: Callable[[mqtt_client.Client, mqtt_client.MQTTMessage], None],
                 log_func):
        """
        mqtt_broker_url: str, the url of the mqtt broker
        mqtt_client_id: str, the client id of the mqtt client
        username: str, the username of the mqtt broker
        password: str, the password of the mqtt broker
        sub_topics: str or list[str], the topics to subscribe, will auto subscribe when everytime get connected to mqtt broker, if use rpc purpose, it should be the one that response message are coming.
        on_msg_received_callback: Callable[[mqtt_client.Client, mqtt_client.MQTTMessage], None], the callback function when a message is received
        log_func: Callable[[str], None], the callback function to log message
        """
        self.mqtt_boker_url = mqtt_broker_url
        self.port = 1883
        self.mqtt_client_id = mqtt_client_id

        self.username = username
        self.password = password

        self.sub_topics = sub_topics

        self.log_func = log_func

        self.online_status_topic = f"dtu_hub/online_status"
        self.client = None
        self.on_msg_received_callback = on_msg_received_callback

    def start_async(self):
        def on_connect(client, userdata, flags, rc, properties):
            if rc == 0 and client.is_connected():
                self.log_func("simple_mqtt_client, Connected to MQTT Broker!")
                # self.client.subscribe(self.sub_topic)

                online_message = {"status": "online", "client_id": self.mqtt_client_id,
                                  "data": {},
                                  "description": f"have been connected to mqtt broker since dtu hub local time: {datetime.datetime.now(datetime.timezone.utc)}"}
                self.client.publish(
                    self.online_status_topic, payload=json.dumps(online_message), qos=1, retain=True)
                if isinstance(self.sub_topics, str):
                    self.client.subscribe(self.sub_topics)
                elif isinstance(self.sub_topics, list):
                    for sub_topic in self.sub_topics:
                        self.client.subscribe(sub_topic)
            else:
                self.log_func(
                    "simple_mqtt_client, Failed to connect, return code %d\n", rc)

        def on_message(client, userdata, msg: mqtt_client.MQTTMessage):
            self.log_func(
                f"simple_mqtt_client, on_message called, topic: {msg.topic}, payload: {msg.payload}")
            if self.on_msg_received_callback:
                self.on_msg_received_callback(self, msg)
            return
            print(
                f"Received `{msg.payload.decode()}` from `{msg.topic}` topic")

        def on_disconnect(client, userdata, disconnectflags, rc, properties):
            self.log_func(
                f"simple_mqtt_client, Disconnected with result code: {rc}")
        self.client = mqtt_client.Client(
            mqtt_client.CallbackAPIVersion.VERSION2, self.mqtt_client_id)
        self.client.username_pw_set(self.username, self.password)
        self.client.on_connect = on_connect
        self.client.on_disconnect = on_disconnect
        self.client.on_message = on_message
        try:
            unplanned_offline_will_message = {"status": "offline", "client_id": self.mqtt_client_id,
                                              "description": f"unplanned disconnected from mqtt broker"}
            self.client.will_set(self.online_status_topic,
                                 payload=json.dumps(unplanned_offline_will_message), qos=1, retain=True)
            # self.client.connect(self.mqtt_boker_url, self.port)
            self.client.connect_async(self.mqtt_boker_url, self.port)
            # break
        except Exception as err:
            self.log_func(
                f"simple_mqtt_client, Failed to connect to broker with error: {err}")
            return False
        self.client.loop_start()
        self.log_func(
            f"simple_mqtt_client, successfully setup mqtt client, client_id: {self.mqtt_client_id}")

    def stop(self):
        planned_offline_message = {"status": "offline", "client_id": self.mqtt_client_id,
                                   "description": f"planned disconnected from mqtt broker at board local time: {datetime.datetime.now()}"}
        self.client.publish(
            self.online_status_topic, payload=json.dumps(planned_offline_message), qos=1, retain=True)
        self.should_stop = True
        if self.client:
            self.client.loop_stop()
            self.client.disconnect()
        # if self.worker_thread:
        #     self.worker_thread.join()

    def send(self, topic: str, msg: Union[str, bytes]) -> bool:
        if not self.client or not self.client.is_connected():
            return False
            raise ValueError("The mqtt client is not connected")

        if isinstance(msg, str):
            msg = msg.encode('utf-8')  # Convert string to bytes

        result = self.client.publish(topic, msg)
        status = result[0]

        if status == 0:
            return True
        else:
            return False

    async def send_async(self, request_topic: str, request_msg: Union[str, bytes],
                         response_topic: str,
                         capture_response: Callable[[Union[str, bytes], bytes, dict], bool],
                         timeout_ms: int) -> Union[str, bytes, None]:
        """
        @param request_topic: str, the topic to send the request
        @param request_msg: Union[str, bytes], the message to send
        @param response_topic: str, the topic to receive the response, must be one of a topic from sub_topics
        @param capture_response: Callable[[str, Union[str, bytes], Union[str, bytes]], bool], the function to check if the response is the expected one, 
            parameters are: raw device request msg, raw device response msg, context
        """
        if not self.client or not self.client.is_connected():
            return None
            raise ValueError("The mqtt client is not connected")
        if isinstance(self.sub_topics, str):
            if response_topic is None:
                response_topic = self.sub_topics
            elif self.sub_topics != response_topic:
                raise ValueError(
                    "The response_topic must be the same as the sub_topic")
        elif isinstance(self.sub_topics, list):
            if response_topic is None:
                response_topic = self.sub_topics[0]
            elif response_topic not in self.sub_topics:
                raise ValueError(
                    "The response_topic must be one of the sub_topics")

        if isinstance(request_msg, str):
            request_msg = request_msg.encode(
                'utf-8')  # Convert string to bytes

        response_future = asyncio.Future()
        loop = asyncio.get_event_loop()

        request_send_timestamp = datetime.datetime.now()

        def on_temp_message(client, userdata, msg: mqtt_client.MQTTMessage):
            # self.log_func(
            #     f"on_temp_message called with topic: {msg.topic}, payload: {msg.payload}")
            if capture_response(request_msg, msg.payload, {"request_send_timestamp": request_send_timestamp}):
                if not response_future.done():
                    # print(f"{datetime.datetime.now()} - set result")
                    loop.call_soon_threadsafe(
                        response_future.set_result, msg.payload)
            else:
                self.log_func(
                    f"simple_mqtt_client, capture_response with failure from topic: {msg.topic}, payload: {msg.payload}")

        try:
            self.client.message_callback_add(response_topic, on_temp_message)
            self.client.publish(request_topic, request_msg)
            response = await asyncio.wait_for(response_future, timeout=timeout_ms / 1000)
        except asyncio.TimeoutError:
            self.log_func(
                f"simple_mqtt_client, Timed out to receive from request_topic: {request_topic}, request_msg: {request_msg}, response_topic: {response_topic}")
            response = None
        finally:
            self.client.message_callback_remove(response_topic)
        return response


if __name__ == "__main__":
    def log_func(msg):
        print(msg)

    mqtt_broker_url = "bs.shaojun.xyz"
    mqtt_client_id = "simple_mqtt_client"
    username = "username"
    password = "password"
    sub_topic = "test"

    def on_msg_received_callback(client, msg: mqtt_client.MQTTMessage):
        print(
            f"Received binary: `{msg.payload}`, decoded: `{msg.payload.decode()}` from `{msg.topic}` topic")
        client.send("dtu_hub_outbox", "Hello from simple mqtt client")
        client.send("dtu_hub_outbox", 0x01)

    async def main():
        client = SimpleMqttClient(
            mqtt_broker_url, mqtt_client_id, username, password, sub_topic, on_msg_received_callback, log_func)
        client.start_async()
        while not client.client.is_connected():
            print("Waiting for mqtt client to connect...")
            await asyncio.sleep(2)
        client.send("dtu_hub_outbox", "Hello from simple mqtt client")

        response = await client.send_async(
            "request_to_topic", "request_message_body", "response_from_topic",
            lambda req_topic, req_msg, msg: msg.topic == "response_from_topic" and msg.payload.decode(
            ) == "expected_response",
            5000
        )
        print(f"Received response: {response}")

        while True:
            await asyncio.sleep(1)

    asyncio.run(main())
