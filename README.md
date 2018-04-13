# Xiaomi Raw

This is a custom component for home assistant to faciliate the reverse engeneering of Xiaomi MiIO devices.

Please follow the instructions on [Retrieving the Access Token](https://home-assistant.io/components/xiaomi/#retrieving-the-access-token) to get the API token to use in the configuration.yaml file.

Credits: Thanks to [Rytilahti](https://github.com/rytilahti/python-miio) for all the work.

## Features

* Power (on, off)
* Sensor value (RSSI in dBm of the WiFi connection)
* Raw command (method + params)
* Set properties (property list)
* Attributes (can be extended by "Set properties")
  - model
  - firmware_version
  - hardware_version
  - properties

## Setup

```yaml
# configuration.yaml

logger:
  default: warn
  logs:
    custom_components.sensor.xiaomi_miio_raw: info
    miio: info

sensor:
  - platform: xiaomi_miio_raw
    name: Any Xiaomi MiIO device
    host: 192.168.130.73
    token: 56197337f51f287d69a8a16cf0677379
    property: 'humidity'
    unit: '%'
```

Configuration variables:
- **host** (*Required*): The IP of your miio device.
- **token** (*Required*): The API token of your miio device.
- **name** (*Optional*): The name of your miio device.
- **property** (*Optional*): Property used as sensor value. WiFi RSSI if unset.
- **unit** (*Optional*): Measurement unit of the property. dBm if unset.

## Debugging

If the custom component doesn't work out of the box for your device please update your configuration to enable a higher log level:

```yaml
# configuration.yaml

logger:
  default: warn
  logs:
    custom_components.sensor.xiaomi_miio_raw: debug
    miio: debug
```

## Platform services

## Platform services

#### Service `sensor.xiaomi_miio_raw_set_properties`

Update the list of the retrieved properties.

| Service data attribute    | Optional | Description                                                                |
|---------------------------|----------|----------------------------------------------------------------------------|
| `entity_id`               |      yes | Only act on a specific fan entity. Else targets all.                       |
| `properties`              |      yes | List of properties. The default is `['power']`                             |


```
# http://localhost:8123/dev-service

Service: sensor.xiaomi_miio_raw_set_properties
Service Data: {"properties":["power","temperature","humidity","aqi"]}
```

#### Service `sensor.xiaomi_miio_raw_command`

Send a command to the device.

| Service data attribute    | Optional | Description                                                                |
|---------------------------|----------|----------------------------------------------------------------------------|
| `entity_id`               |      yes | Only act on a specific fan entity. Else targets all.                       |
| `method`                  |       no | Method name of the command. Example: `set_power`                           |
| `params`                  |      yes | List of parameters. Example: `['on']`                                      |


```
# http://localhost:8123/dev-service

# Turn the device on
Service: sensor.xiaomi_miio_raw_command
Service Data: {"method":"set_power","params":["on"]}

# Turn the device off
Service: sensor.xiaomi_miio_raw_command
Service Data: {"method":"set_power","params":["off"]}

# Request some properties
Service: sensor.xiaomi_miio_raw_command
Service Data: {"method":"get_prop","params":["power","temperature","humidity","aqi"]}
```

#### Service `sensor.xiaomi_miio_raw_turn_on`

Turn the device on.

| Service data attribute    | Optional | Description                                                          |
|---------------------------|----------|----------------------------------------------------------------------|
| `entity_id`               |      yes | Only act on a specific xiaomi miio entity. Else targets all.         |

#### Service `sensor.xiaomi_miio_raw_turn_off`

Turn the device off.

| Service data attribute    | Optional | Description                                                          |
|---------------------------|----------|----------------------------------------------------------------------|
| `entity_id`               |      yes | Only act on a specific xiaomi miio entity. Else targets all.         |

