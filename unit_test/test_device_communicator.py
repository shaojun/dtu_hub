
import asyncio
import datetime
from itertools import groupby
import time
import unittest
from unittest.mock import MagicMock, patch
from logging import Logger
from device.communicator import DeviceCommunicator
from models import REQUEST_ACTION, SUB_DEVICE_TYPE, DeviceRequest, SubDeviceResponse


class TestDeviceCommunicator(unittest.TestCase):
    def setUp(self):
        self.logger = MagicMock(spec=Logger)
        self.communicator = DeviceCommunicator()
        self.communicator.start()
        time.sleep(2)  # Wait for the MQTT client to connect

    def test_send_async__single_request_GPS_EBYTE_E108_D01__Read(self):
        dtu_sn = "02500924101100024659"

        async def run_test():
            request = DeviceRequest(
                request_action=REQUEST_ACTION.Read,
                id="1",
                dtu_sn=dtu_sn,
                physical_id="001",
                device_type=SUB_DEVICE_TYPE.GPS_EBYTE_E108_D01,
                data={},
                description="Test request"
            )

            response = self.communicator.send_request(request, 6000)

            self.assertIsInstance(response, SubDeviceResponse)
            print(f"see SubDeviceResponse-> {response}")

            current_year = datetime.datetime.now().year
            current_month = datetime.datetime.now().month
            current_day = datetime.datetime.now().day
            current_hour_utc0 = datetime.datetime.now(
                datetime.timezone.utc).hour

            self.assertEqual(response.data["is_location_valid"], True)
            self.assertEqual(response.data["year"], current_year)
            self.assertEqual(response.data["month"], current_month)
            self.assertEqual(response.data["day"], current_day)
            self.assertEqual(response.data["hour"], current_hour_utc0)
        asyncio.run(run_test())

    def test_send_async__multiple_request_GPS_EBYTE_E108_D01__Read(self):
        dtu_sn = "02500924101100024659"

        async def run_test():
            send_times = 5
            response_list = []
            real_total_used_time_by_ms = 0
            for i in range(send_times):
                request = DeviceRequest(
                    request_action=REQUEST_ACTION.Read,
                    id=str(i),
                    dtu_sn=dtu_sn,
                    physical_id=f"00{i}",
                    device_type=SUB_DEVICE_TYPE.GPS_EBYTE_E108_D01,
                    data={},
                    description=f"Test request: {i}"
                )

                start_time = time.time()
                response = self.communicator.send_request(request, 6000)
                print(f"got SubDeviceResponse[{i}] -> {response}")
                used_time_by_ms = (time.time() - start_time) * 1000
                real_total_used_time_by_ms += used_time_by_ms
                response_list.append(response)
                await asyncio.sleep(1)
            await asyncio.sleep(5)
            print(f"real_total_used_time_by_ms: {real_total_used_time_by_ms}")
            self.assertEqual(len(response_list), send_times)

            # group by `id` from response_list
            response_list.sort(key=lambda x: x.id)
            group_by_id_result = {k: list(v) for k, v in groupby(
                response_list, key=lambda x: x.id)}
            self.assertEqual(len(group_by_id_result), send_times)

            # group by `physical_id` from response_list
            response_list.sort(key=lambda x: x.physical_id)
            group_by_physical_id_result = {k: list(v) for k, v in groupby(
                response_list, key=lambda x: x.physical_id)}
            self.assertEqual(len(group_by_physical_id_result), send_times)

            current_year = datetime.datetime.now().year
            current_month = datetime.datetime.now().month
            current_day = datetime.datetime.now().day
            current_hour_utc0 = datetime.datetime.now(
                datetime.timezone.utc).hour
            for response in response_list:
                self.assertIsInstance(response, SubDeviceResponse)
                self.assertEqual(response.data["is_location_valid"], True)
                self.assertEqual(response.data["year"], current_year)
                self.assertEqual(response.data["month"], current_month)
                self.assertEqual(response.data["day"], current_day)
                self.assertEqual(response.data["hour"], current_hour_utc0)
        asyncio.run(run_test())


if __name__ == '__main__':
    unittest.main()
