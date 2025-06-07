# Modbus-Connected-Home
Управляет DIO через Modbus. Пока тестируется.

Должен быть файл в расположении: /config/modbus/poller.yaml
Содержимое:
  mqtt_broker: 172.30.32.1
  mqtt_port: 1883
  device: /dev/ttyUSB0
  username: modbus
  passwd: modbus
  slaves:
    -
      period: 2
      alias: DIO
      slave_id: 1
      data:
        discrete_inputs:
          count: 32
        coils:
          count: 16
      topics:
      - mb/1/15/0
      - mb/1/15/1
      - mb/1/15/2
      - mb/1/15/3
      - mb/1/15/4
      - mb/1/15/5
      - mb/1/15/6
      - mb/1/15/7
      - mb/1/15/8
      - mb/1/15/9
      - mb/1/15/10
      - mb/1/15/11
      - mb/1/15/12
      - mb/1/15/13
      - mb/1/15/14
      - mb/1/15/15
      - mb/1/02/0
      - mb/1/02/1
      - mb/1/02/2
      - mb/1/02/3
      - mb/1/02/4
      - mb/1/02/5
      - mb/1/02/6
      - mb/1/02/7
      - mb/1/02/8
      - mb/1/02/9
      - mb/1/02/10
      - mb/1/02/11
      - mb/1/02/12
      - mb/1/02/13
      - mb/1/02/14
      - mb/1/02/15
      - mb/1/02/16
      - mb/1/02/17
      - mb/1/02/18
      - mb/1/02/19
      - mb/1/02/20
      - mb/1/02/21
      - mb/1/02/22
      - mb/1/02/23
      - mb/1/02/24
      - mb/1/02/25
      - mb/1/02/26
      - mb/1/02/27
      - mb/1/02/28
      - mb/1/02/29
      - mb/1/02/30
      - mb/1/02/31
      
