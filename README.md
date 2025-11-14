# DTU USR-DR154/152
For demestic use this model wtih `DR154`, `RS485`, `棒状天线`    
![image](https://github.com/user-attachments/assets/31b3535b-a52b-4716-b68a-61765dc809b5)

regist an account on `https://dm.usr.cn/`, and later will bind the `DTU` under it.
## Config DTU via phone
* power on 4G DTU    
  ![image](https://github.com/user-attachments/assets/1b33e763-8474-403c-9cf6-cf97dee54bb9)    
  when powered on, the DTU shows:    
  > should see `POW` led goes to steady red.    
  > should see `NET` led goes to steady green.    
  > should see `LINKA` led goes to steady green.    
* use phone to scan config QR code
    ![image](https://github.com/user-attachments/assets/12907319-a13d-4f92-a02f-ada83585ea3a)
* config parameters    
  the key value is the `SN` which will be used in many parameters, so copy it.    
  refer and replace all sample `SN` values from below:    
  ![8a8f77c68c41ba72a73b87d792221ea](https://github.com/user-attachments/assets/d9ece8c1-79ae-4648-b2cb-210462b30fbe)

  should see `WORK` led goes to blinking green.

* double check at `usr.cn`    
  access `https://dm.usr.cn/#/cloud/gateway/ViewGatewayList`
  should see the `DTU` already there with state: `在线`:    
  ![image](https://github.com/user-attachments/assets/2c1eef66-22c4-485e-8691-d549ab3106c2)

  and `view/edit` detail parameters:    
  ![image](https://github.com/user-attachments/assets/3fbb9cc6-4af6-480b-a445-f1e06d81bac1)

# Devices
## GPS - EBYTE_E108_D01
### Setup
* install `antenna`    
  ![image](https://github.com/user-attachments/assets/a90c98bb-4f05-4a4a-9c1a-e828e682750f)    
  make sure the `antenna` is placed at outdoor area:    
  ![image](https://github.com/user-attachments/assets/4fd0d21c-1eb0-494b-867d-756dd887fc57)

* connect GPS module to `DTU`
  follow `A to A`, `B to B`:    
  ![image](https://github.com/user-attachments/assets/6d7ede9e-576b-4433-8046-85cc0d708f59)

* power on GPS module
### Test
access `DTU_HUB` debug page: `http://do.bugbug.fun:8000/docs#/default/send_sub_device_request_sub_device_request_post`    
![image](https://github.com/user-attachments/assets/de957e9f-ee48-420d-a311-c4304d66985b)    
    
send request by replacing your `SN` of the `4G DTU`:
```
{
  "id": "string",
  "dtu_sn": "02500924101100024659",
  "physical_id": "1",
  "device_type": "GPS_EBYTE_E108_D01",
  "request_type": "Read",
  "data": {},
  "description": "string"
}
```
should see response like:
```
{
  "id": "string",
  "dtu_sn": "02500924101100024659",
  "physical_id": "1",
  "device_type": "GPS_EBYTE_E108_D01",
  "request_type": "Read",
  "overall_state_code": 200,
  "description": "Success",
  "data": {
    "is_location_valid": true,
    "year": 2024,
    "month": 11,
    "day": 26,
    "hour": 4,
    "min": 8,
    "sec": 42,
    "longitude_heading": "E",
    "longitude": 121.57868957519531,
    "latitude_heading": "N",
    "latitude": 31.156400680541992,
    "speed_to_ground": 0,
    "heading_to_ground": 338.9200134277344
  }
}
```
this is the sample of response:    
![image](https://github.com/user-attachments/assets/1aedb12b-1f46-4f89-a445-2ab2af882d7d)

  
## Probe - Probe_YiTong_TankTruck
### Setup
* connect Probe to `DTU`
  follow `Probe Yellow to DTU A`, `Probe Blue to DTU B`:  
  ![image](https://github.com/user-attachments/assets/b841a852-afb0-4193-99e1-2d9befd3ddb5)

* power on Probe
### Test
as Probe default use `baud rate 2400`, so **change** the `DTU` config to use same baud rate is necessary:    
![image](https://github.com/user-attachments/assets/e36d9955-28d4-4e2d-aab2-2b2277315c88)    


access `DTU_HUB` debug page: `http://do.bugbug.fun:8000/docs#/default/send_sub_device_request_sub_device_request_post`    
![image](https://github.com/user-attachments/assets/daf7db8b-d517-4c37-acd1-7073ed534275)

    
send request by replacing your `SN` of the `4G DTU`:
```
{
  "id": "string",
  "dtu_sn": "02500924101100024659",
  "physical_id": "1",
  "device_type": "Probe_YiTong_TankTruck",
  "request_type": "Read",
  "data": {},
  "description": "string"
}
```
should see response like:
```
{
  "id": "string",
  "dtu_sn": "02500924101100024659",
  "physical_id": "1",
  "device_type": "Probe_YiTong_TankTruck",
  "request_type": "Read",
  "overall_state_code": 200,
  "description": "Success",
  "data": {
    "类别号": 1,
    "探棒号": 1,
    "探棒类型": 2,
    "M1": 0,
    "M2": 999999,
    "M3": 0,
    "温度点数": 2,
    "温度": [
      {
        "温度A": 19.099999999999994,
        "温度B": 20.099999999999994
      }
    ]
  }
}
```
# other DTU_HUB command
## modify baud rate of `EBYTE_E108_D01 GPS`
the `EBYTE_E108_D01 GPS` default use baud rate 9600, so onced changed the DTU to use `baud rate 2400` for compatible with `Probe YiTong_TankTruck` will cause the communication down to GPS.    
The solution is to udpate GPS module to use `baud rate 2400` as well.    
**make sure** you have successful commu with GPS, then change `EBYTE_E108_D01 GPS` to use `baud rate 2400` via command:
```
{
  "id": "string",
  "dtu_sn": "02500924101100024659",
  "physical_id": "1",
  "device_type": "GPS_EBYTE_E108_D01",
  "request_type": "Write",
  "data": {},
  "description": "string"
}
```
## read `EBYTE_E108_D01 GPS` baud rate:
```
{
  "id": "string",
  "dtu_sn": "02500924101100024659",
  "physical_id": "1",
  "device_type": "GPS_EBYTE_E108_D01",
  "request_type": "Read_Advanced",
  "data": {},
  "description": "string"
}
```
sample response of it using `baud rate 2400`:
```
{
  "id": "string",
  "dtu_sn": "02500924101100024659",
  "physical_id": "1",
  "device_type": "GPS_EBYTE_E108_D01",
  "request_type": "Read_Advanced",
  "overall_state_code": 200,
  "description": "Success",
  "data": {
    "baud_rate": 2400
  }
}
```
## reset `EBYTE_E108_D01 GPS` to use `baud rate 9600`:
NOTE, once the reset done, if your DTU is not using baud rate 9600, you'll lose communication to GPS!!!   
```
{
  "id": "string",
  "dtu_sn": "02500924101100024659",
  "physical_id": "1",
  "device_type": "GPS_EBYTE_E108_D01",
  "request_type": "ReWrite",
  "data": {},
  "description": "string"
}
```

# DTU USR-G780s
## 基本设置
其中`02500525102900023669`为此`DTU`的`SN`唯一码:    

<img width="400" height="600" alt="image" src="https://github.com/user-attachments/assets/e55bee67-feaf-4830-b12a-b8aad0516a3d" />
<img width="300" height="300" alt="image" src="https://github.com/user-attachments/assets/3851f2ad-8bfe-4b14-bfd9-7927792944e0" />
<img width="300" height="300" alt="image" src="https://github.com/user-attachments/assets/e48f215b-2bcc-46df-8fb6-f6f834b8f65e" />

### 发布
```
MQTT1 发布主题1：
开

发布主题1 Topic：
/PubTopic/02500525102900023669

发布主题1 QoS：
0

发布主题1 消息保留：
开
```
### 心跳消息
```
启用心跳包：
开

心跳间隔时间：
30秒

心跳发送方向：
向服务器发送心跳包

心跳数据类型：
LBS信息
```

## 消息示例
### timely heartbeat
```
Topic: /PubTopic/02500525102900023669QoS: 0

LNG = 112.12719727, LAT = 29.10926628, TIME = 2025-11-11 11:04:33
```
### when powered off dtu
```
Topic: /PubTopic/02500525102900023669QoS: 0

02500525102900023669:POWER_OFF
```

