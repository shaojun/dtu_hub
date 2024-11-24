import time
from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from datetime import datetime, timedelta, timezone
from jose import JWTError, jwt
from enum import Enum
import logging
from logging.handlers import TimedRotatingFileHandler
from pydantic import BaseModel

from device.communicator import DeviceCommunicator
from models import *
from device.simple_mqtt_client import SimpleMqttClient
from logging_config import setup_logging

# Setup logging
logger = setup_logging()

deviceCommunicator = DeviceCommunicator(logger)
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


@app.get("/dtu_state/{dtu_sn}")
async def get_dtu_state(dtu_sn: str, token: str = Depends(oauth2_scheme)) -> DTU_DEVICE_STATE:
    logger.debug(f"Getting DTU state for: {dtu_sn}")
    # ...existing code...
    return DTU_DEVICE_STATE.Unknown  # Placeholder return value


@app.get("/sub_device_state/{device_id}")
async def get_sub_device_state(device_id: str, token: str = Depends(oauth2_scheme)) -> SUB_DEVICE_STATE:
    logger.debug(f"Getting sub device state for: {device_id}")
    # ...existing code...
    return SUB_DEVICE_STATE.Unknown  # Placeholder return value


@app.post("/sub_device_request")
async def send_sub_device_request(request: SubDeviceRequest, token: str = Depends(oauth2_scheme)) -> SubDeviceResponse:
    logger.debug(f"Sending request to sub device: {request}")
    response = await deviceCommunicator.send_async(request, 6000)
    return response

if __name__ == "__main__":
    logger.info("Starting DTU Hub...")
    deviceCommunicator.init()
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
