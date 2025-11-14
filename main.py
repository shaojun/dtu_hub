import time
from typing import List
import uuid
from fastapi import FastAPI, Depends, HTTPException, status, Request
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from datetime import datetime, timedelta, timezone
from jose import JWTError, jwt
from enum import Enum
import logging.config
import logging
from logging.handlers import TimedRotatingFileHandler
from pydantic import BaseModel
import yaml
from threading import Lock

from models import *
from device.simple_mqtt_client import SimpleMqttClient
from fastapi.middleware import Middleware
from fastapi.middleware.httpsredirect import HTTPSRedirectMiddleware
from paho.mqtt.client import PayloadType
from device.protocol_parser.parser import DeviceProtocolParser
import inspect
with open('log_config.yaml', 'r') as f:
    config = yaml.safe_load(f.read())
    logging.config.dictConfig(config)


def _initialize_protocol_parsers() -> list[DeviceProtocolParser]:
    parser_classes = [
        cls for _, cls in inspect.getmembers(
            __import__('device.protocol_parser.parser', fromlist=['']),
            lambda member: inspect.isclass(member) and issubclass(
                member, DeviceProtocolParser) and member is not DeviceProtocolParser
        )
    ]
    return [parser_class() for parser_class in parser_classes]


# Setup logging
main_logger = logging.getLogger("mainLogger")

device_protocol_parsers: list[DeviceProtocolParser] = _initialize_protocol_parsers(
)
devices: list[DeviceDigitalTwin] = []


def on_msg_from_dtu_callback(topic: str, raw_msg: PayloadType):
    main_logger.info(f"Received message on topic {topic}: {raw_msg}")
    # if topic is like dtu/02500525102900023669/outbox
    # dtu_sn = topic.split('/')[1]
    for parser in device_protocol_parsers:
        device_identity, data_record = parser.TryParse(topic, raw_msg)
        if device_identity is None:
            continue
        existing_device_updated = False
        for device in devices:
            if device.equals_to_device_identity(device_identity):
                existing_device_updated = True
                device.last_device_msg_received_datetime = datetime.now(
                    timezone.utc)
                device.data_records.append(data_record)
                # Keep only the latest N records
                if len(device.data_records) > parser.max_keep_data_records_count:
                    device.data_records = device.data_records[-parser.max_keep_data_records_count:]
        if not existing_device_updated:
            new_device = DeviceDigitalTwin(
                device_identity=device_identity,
                last_device_msg_received_datetime=datetime.now(timezone.utc),
                data_records=[data_record],
            )
            devices.append(new_device)


simple_mqtt_client = SimpleMqttClient(
    host="daefcc-cloud.top",
    port=1883,
    name="MainSimpleMqttClient",
    mqtt_client_id=f"main_simple_mqtt_client_{uuid.getnode()}",
    username="test_user",
    password="test_pass",
    on_message_callback=on_msg_from_dtu_callback,
    logger=main_logger,
    description="DTU Hub Main Simple MQTT Client",
)

simple_mqtt_client.subscribe("dtu/+/outbox")
app = FastAPI()

# Hardcoded credentials
USERNAME = "user"
PASSWORD = "password"
SECRET_KEY = "secret"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60*24  # 24 hours

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")


def authenticate_user(username: str, password: str):
    if username == USERNAME and password == PASSWORD:
        return True
    return False


def create_access_token(data: dict, expires_delta: timedelta = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=15)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


async def get_current_user(token: str = Depends(oauth2_scheme)):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception
    if username != USERNAME:
        raise credentials_exception
    return username


@app.post("/token", tags=["auth"])
async def login_for_access_token(form_data: OAuth2PasswordRequestForm = Depends()):
    if not authenticate_user(form_data.username, form_data.password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": form_data.username}, expires_delta=access_token_expires
    )
    return {"access_token": access_token, "token_type": "bearer"}


@app.get("/device_data/")
async def query_device_data(
        dtu_sn: Optional[str] = "02500525102900023669",
        device_type: Optional[DEVICE_TYPE] = None,
        device_physical_id: Optional[str] = None,
        token: str = Depends(oauth2_scheme)) -> List[DeviceDigitalTwin]:
    result_devices = []
    for device in devices:
        if device.device_identity.dtu_sn != dtu_sn:
            continue
        if device_type is not None and device.device_identity.device_type != device_type:
            continue
        if device_physical_id is not None and device.device_identity.device_physical_id != device_physical_id:
            continue
        result_devices.append(device)
    return result_devices


# Dictionary to store locks for each dtu_sn
dtu_locks = {}
# Global lock to synchronize access to dtu_locks
global_lock = Lock()


@app.post("/device_request")
async def send_device_request(request: DeviceRequest, token: str = Depends(oauth2_scheme)):
    target_dtu_sn = request.device_identity.dtu_sn
    main_logger.debug(f"Sending device request: {request}")

    try:
        parser = next(
            (parser for parser in device_protocol_parsers if request.device_identity.device_type.value in parser.__class__.__name__), None)
        if parser is None:
            raise ValueError(
                f"Could not find parser for device type {request.device_identity.device_type}")
        try:
            raw_msg = parser.Serialize(request)
        except Exception as e:
            raise ValueError(
                f"Failed to serialize request for device type {request.device_identity.device_type} with parser, detail: {str(e)}")
        simple_mqtt_client.publish(
            f"dtu/{request.device_identity.dtu_sn}/inbox", raw_msg)
    except Exception as e:
        main_logger.exception(
            f"Error processing request for DTU {target_dtu_sn}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Internal server error while processing request for DTU {target_dtu_sn}, detail: {str(e)}"
        )


@app.middleware("http")
async def log_request_data(request: Request, call_next):
    client_ip = request.client.host
    user_agent = request.headers.get('user-agent', 'unknown')
    main_logger.info(
        f"Handle HTTP Request from {client_ip} with User-Agent: {user_agent}")
    response = await call_next(request)
    return response

if __name__ == "__main__":
    try:
        main_logger.info("Starting DTU Hub...")
        simple_mqtt_client.connect()
        import uvicorn
        # Specify the number of worker threads
        uvicorn.run(app, host="0.0.0.0", port=8000)
    except Exception as e:
        main_logger.exception("Failed to start DTU Hub")
        raise
