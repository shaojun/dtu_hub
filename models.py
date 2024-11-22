from enum import Enum
from typing import Optional, Union

from pydantic import BaseModel


class DTU_DEVICE_STATE(str, Enum):
    Online = "Online"
    Offline = "Offline"
    Unknown = "Unknown"


class SUB_DEVICE_STATE(str, Enum):
    Online = "Online"
    Offline = "Offline"
    Unknown = "Unknown"
    Unsupport = "Unsupport"


class SUB_DEVICE_TYPE(str, Enum):
    GPS_EBYTE_E108_D01 = "GPS_EBYTE_E108_D01"
    Probe_YiTong_TankTruck = "Probe_YiTong_TankTruck"


class REQUEST_TYPE(str, Enum):
    Read = "Read",
    Read_Advanced = "Read_Advanced",


class SubDeviceRequest(BaseModel):
    id: str
    dtu_sn: str
    physical_id: str
    device_type: SUB_DEVICE_TYPE
    request_type: REQUEST_TYPE
    data: dict
    description: str


class SubDeviceResponse(BaseModel):
    id: str
    dtu_sn: str
    physical_id: str
    device_type: SUB_DEVICE_TYPE
    request_type: REQUEST_TYPE
    # only 200 means success
    overall_state_code: int = 200
    description: str = "Success"
    data: Optional[dict] = None
