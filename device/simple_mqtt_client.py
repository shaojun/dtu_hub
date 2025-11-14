from ast import Tuple
import asyncio
import json
import uuid
from datetime import datetime, timezone
import paho.mqtt.client as mqtt
from typing import Callable, Any, Dict, Optional, Union
import time
import logging
from paho.mqtt.enums import CallbackAPIVersion
from paho.mqtt.client import PayloadType


class SimpleMqttClient:
    def __init__(self,
                 host="ai.visitpark.cn",
                 port=1883,
                 name: str = None,
                 mqtt_client_id: str = None,
                 username=None,
                 password=None,
                 on_message_callback: Callable[[str, PayloadType], None] = None,
                 logger: logging.Logger = None,
                 description: str = "") -> None:
        """
        :param host: The hostname of the MQTT broker.
        :param port: The port of the MQTT broker.
        :param name: The name of the client, used in logging and online status topic.
        :param mqtt_client_id: The client ID to use when connecting to the broker, must be unique.
        :param username: The username to use when connecting to the broker.
        :param password: The password to use when connecting to the broker.
        :param on_message_callback: A callback function to handle incoming messages, should accept two parameters: topic and payload, DO NOT BLOCK in this callback, as it runs in MQTT client thread, use threadpool or asyncio to handle long-running tasks.
        :param logger: A logger instance to use for logging, if None, a default logger will be created.
        :param description: A description of the purpose of this client, used in logging and online status.
        """
        if not name:
            raise Exception("name must be provided")
        if logger is None:
            logger = logging.getLogger(__class__.__name__+"Logger")
        self.logger = logger
        self.host = host
        self.port = port
        self.name = name
        self.description = description

        mqtt_client_id = mqtt_client_id or f"simple_mqtt_rpc_{name}_{uuid.uuid4().hex[:8]}"
        # Initialize MQTT client
        self.client = mqtt.Client(
            callback_api_version=CallbackAPIVersion.VERSION2,
            client_id=mqtt_client_id)
        if username and password:
            self.client.username_pw_set(username, password)

        # Set up client callbacks
        self.client.on_connect = self._on_connect
        self.client.on_disconnect = lambda client, userdata, disconnect_flags, reason_code, properties: print(
            f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S %f')} - {self.name}, Disconnected from MQTT broker")
        self.client.on_message = self._on_message

        self.subscribed_topics: list[str] = []
        self.on_message_callbacks: list[Callable[[str, str], None]] = []
        if on_message_callback:
            self.on_message_callbacks.append(on_message_callback)

        self.online_status_topic = f"rpc/rpc_client/{name}/online_status"

    def connect(self) -> bool:
        """Connect to the MQTT broker, will not block, the connection will be established in the background"""
        print(
            f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S %f')} - {self.name}, Connecting to MQTT broker: {self.host}:{self.port}")
        try:
            unplanned_offline_will_message = {"status": "offline", "name": self.name,
                                              "reason": f"unplanned disconnected from mqtt broker",
                                              "description": self.description or ""
                                              }
            self.client.will_set(self.online_status_topic,
                                 payload=json.dumps(unplanned_offline_will_message), qos=1, retain=True)

            self.client.connect_async(self.host, self.port)
            self.client.loop_start()
            return True
        except Exception as e:
            print(
                f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S %f')} - {self.name}, Failed to connect to MQTT broker: {e}")
            self.logger.exception(
                f"{self.name} - Failed to connect to MQTT broker: {e}")
            return False

    def disconnect(self) -> None:
        print(
            f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S %f')} - SimpleMqttClient - {self.name}, planned Disconnecting from MQTT broker")
        self.logger.info(
            f"SimpleMqttClient - {self.name} - planned Disconnecting from MQTT broker")
        planned_offline_message = {"status": "offline", "name": self.name,
                                   "reason": f"planned disconnected from mqtt broker at local time: {datetime.now(timezone.utc).isoformat()}",
                                   "description": self.description or ""
                                   }
        self.client.publish(
            self.online_status_topic, payload=json.dumps(planned_offline_message), qos=1, retain=True)

        """Disconnect from the MQTT broker"""
        self.client.loop_stop()
        self.client.disconnect()

    def _on_connect(self, client, userdata, flags, rc, prop):
        """Callback for when the client connects to the broker
        "Client", Any, ConnectFlags, ReasonCode, Union[Properties, None]
        """
        if rc == 0:
            print(
                f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S %f')} - {self.name}, Connected to MQTT broker: {self.host}:{self.port}")
            self.logger.info(
                f"{self.name} - Connected to MQTT broker: {self.host}:{self.port}")
            online_message = {"status": "online", "name": self.name,
                              "data": {},
                              "reason": f"have been connected to mqtt broker since local time: {datetime.now(timezone.utc).isoformat()}",
                              "description": self.description or ""
                              }
            self.client.publish(
                self.online_status_topic, payload=json.dumps(online_message), qos=1, retain=True)

            if self.subscribed_topics:
                for tp in self.subscribed_topics:
                    client.subscribe(tp)
        else:
            print(
                f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S %f')} - {self.name}, Failed to connect to MQTT broker with code: {rc}")
            self.logger.error(
                f"{self.name} - Failed to connect to MQTT broker with code: {rc}")

    def _on_message(self, client, userdata, msg):
        """Callback for when a message is received from the broker"""
        try:
            payload = msg.payload
            # print(
            #     f"{datetime.now().strftime('%H:%M:%S %f')} - {self.name} - SimpleMqttClient, Received message from topic {msg.topic}: {str(payload)[0:180]}")
            topic = msg.topic
            for callback in self.on_message_callbacks:
                callback(topic, payload)
        except json.JSONDecodeError:
            print(
                f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S %f')} - {self.name} - SimpleMqttClient, Failed to decode JSON message from topic {msg.topic}")
            self.logger.error(
                f"{self.name} - SimpleMqttClient -Failed to decode JSON message from topic {msg.topic}")
        except Exception as e:
            # get stack trace and log it
            import traceback
            print(
                f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S %f')} - {self.name} - SimpleMqttClient, Failed to handle message: {e} from topic {msg.topic}")
            self.logger.exception(
                f"{self.name} - SimpleMqttClient - Failed to handle message: {e} from topic {msg.topic}")

    def subscribe(self, topic: str):
        """
        handle message from topic `topic`
        the callback's first input is the source topic, the second input is the event body.
        """
        if not topic:
            raise Exception("topic must be provided")
        if self.client.is_connected():
            self.client.subscribe(topic)
        self.subscribed_topics.append(topic)

    def publish(self,
                topic: str,
                msg: PayloadType) -> bool:
        if not topic:
            raise Exception("topic must be provided")

        try:
            ret = self.client.publish(topic, msg, qos=0)
            # print(
            #     f"{datetime.now().strftime('%H:%M:%S %f')} - {self.name} - SimpleMqttClient, Published(msg len: {len(json.dumps(msg))}) with result: {ret.rc.name}, {topic}-> {str(msg)[0:200]}")
            # qos 0 always has the is_published() as False, and infinite timeout of wait_for_publish, so we don't need to wait for it.
            # if not ret.is_published():
            #     ret.wait_for_publish(timeout=5)
            #     print(
            #         f"{datetime.now().strftime('%H:%M:%S %f')} - {self.name} - SimpleMqttClient, wait_for_publish Message sent to topic {topic} successfully")
            # Ensure message is sent before proceeding
            if ret.rc != mqtt.MQTT_ERR_SUCCESS:
                print(
                    f"{datetime.now().strftime('%H:%M:%S %f')} - {self.name} - SimpleMqttClient, Failed to publish message to topic {topic}: {ret.rc.name}")
                self.logger.error(
                    f"{self.name} - Failed to publish message to topic {topic}: {ret.rc.name}")
                return False
            return True
        except Exception as e:
            print(
                f"{datetime.now().strftime('%H:%M:%S %f')} - {self.name} - SimpleMqttClient, Failed to publish message to topic {topic}: {e}")
            self.logger.exception(
                f"{self.name} - SimpleMqttClient - Failed to publish message to topic {topic}: {e}")
            return False

    def send_request(
            self,
            request_to_topic: str, response_from_topic: str,
            msg: PayloadType,
            capture_response: Callable[[Union[str, bytes], bytes, dict], bool],
            timeout: int = 3000) -> Optional[Dict]:
        """
        发送请求到指定的topic, 然后等待响应, 超时返回None.
        这是一个blocking call, 会阻塞当前线程, 直到收到响应或者超时.
        @param request_to_topic: The topic to send the request to.
        @param response_from_topic: The topic to receive the response from.
        @param request_id: The ID of the request.
        @param action: The action name for the request.
        @param msg: The sending msg, default is None.
        @param timeout: The timeout for the request in milliseconds, default is 3000.
        @return: The response from the remote peer, or None if timed out.

        @return: response
        """
        if not self.client.is_connected():
            self.logger.error(f"{self.name} - Not connected to MQTT broker")
            raise Exception(f"{self.name} - Not connected to MQTT broker")

        # Store response in a dict that can be accessed from the callback
        response_container = {"response": None}
        response_received = False
        request_send_timestamp = datetime.now()
        # Create an event to signal when response is received
        import threading
        response_event = threading.Event()

        # Create temporary callback function to handle the response
        def temp_callback(topic: str, payload: PayloadType):
            # Skip if topic doesn't match
            if topic != response_from_topic:
                return

            if not capture_response(msg, payload,
                                    {"request_send_timestamp": request_send_timestamp,
                                     "request_topic": request_to_topic}):
                return

            # We found our response
            response_container["response"] = payload
            response_event.set()

        # Add temporary callback and subscribe to response topic
        self.on_message_callbacks.append(temp_callback)
        was_already_subscribed = response_from_topic in self.subscribed_topics
        if not was_already_subscribed:
            self.subscribe(response_from_topic)
            # Small delay to ensure subscription is registered before sending request
            import time
            time.sleep(0.1)

        try:
            # Publish request
            result = self.client.publish(request_to_topic, msg)
            # Ensure message was published before waiting for response
            # result.wait_for_publish()

            # Wait for response with timeout
            response_received = response_event.wait(timeout / 1000)

            if response_received:
                return response_container["response"]
            else:
                self.logger.warning(
                    f"{self.name} - Request timed out")
                return None

        finally:
            # Clean up: remove callback and unsubscribe if we subscribed
            try:
                if temp_callback in self.on_message_callbacks:
                    self.on_message_callbacks.remove(temp_callback)
            except ValueError:
                # Callback might have been removed already
                pass

            # Only unsubscribe if we weren't already subscribed and no other request is using this topic
            if not was_already_subscribed and response_from_topic in self.subscribed_topics:
                # Don't unsubscribe immediately as other concurrent requests might be using this topic
                # Just remove from our tracking list
                pass
