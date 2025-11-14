from datetime import datetime, timezone
from enum import Enum
from typing import List, Optional, Union

from pydantic import BaseModel

class DEVICE_TYPE(str, Enum):
    DTU = "DTU"

    SUB_DEVICE__Probe_YiTong_TankTruck = "Probe_YiTong_TankTruck"


class REQUEST_ACTION(str, Enum):
    Read = "Read",
    Read_Advanced = "Read_Advanced",
    Write = "Write",
    ReWrite = "ReWrite",


class DeviceIdentity(BaseModel):
    name: str

    # both dtu and sub-device should have unique dtu_sn
    dtu_sn: str
    # state: DEVICE_STATE
    device_type: DEVICE_TYPE
    # likely only sub-device uses this field
    device_physical_id: Optional[str] = None


class DeviceRequest(BaseModel):
    device_identity: DeviceIdentity = DeviceIdentity(
        name="",
        dtu_sn="02500525102900023669",
        device_type=DEVICE_TYPE.SUB_DEVICE__Probe_YiTong_TankTruck,
        device_physical_id="1",
    )
    request_action: REQUEST_ACTION = REQUEST_ACTION.Read
    data: Optional[dict] = None


# class SubDeviceResponse(BaseModel):
#     id: str
#     dtu_sn: str
#     physical_id: str
#     device_type: DEVICE_TYPE
#     request_type: REQUEST_ACTION
#     # only 200 means success
#     overall_state_code: int = 200
#     description: str = "Success"
#     data: Optional[dict] = None


class DeviceDigitalTwin(BaseModel):
    device_identity: DeviceIdentity

    last_device_msg_received_datetime: Optional[datetime] = None
    description: Optional[str] = None
    data_records: Optional[List[dict]] = []

    def equals_to_device_identity(self, device_identity: DeviceIdentity) -> bool:
        return self.device_identity.dtu_sn == device_identity.dtu_sn and \
            self.device_identity.device_type == device_identity.device_type and \
            self.device_identity.name == device_identity.name and \
            self.device_identity.device_physical_id == device_identity.device_physical_id
