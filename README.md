# Xiaomi MIoT Raw

这个插件修改自 [syssi](https://github.com/syssi) 的 [xiaomi_raw](https://github.com/syssi/xiaomi_raw)，目的是支持小米新版的 MioT 协议。这样，一些功能简单的智能设备便可以快速高效地接入 HA，而不必再拘泥于设备型号、不必再等待别人去写插件适配了。

插件的使用方法与原插件大同小异。有关配置文件格式，请参阅根目录下的 ``config_example.yaml`` 文件。

如果对您有帮助，欢迎给个 Star！ 🌟 

## 功能

* 通过 ``switch`` 控制设备开关
* 通过 ``sensor`` 获取设备的属性值
* 发送原始命令 (尚未测试是否可用)

## 安装

* 将 custom_component 文件夹中的内容拷贝至自己的相应目录

或者
* 将此 repo ([https://github.com/ha0y/xiaomi_miot_raw](https://github.com/ha0y/xiaomi_miot_raw)) 添加到 [HACS](https://hacs.xyz/)，然后添加“Xiaomi MiOT Raw”


## 配置文件

```yaml
请参考 config_example.yaml

```

Sensor 的配置参数:
- **host** (*Required*): 设备 IP.
- **token** (*Required*): 设备 token.
- **name** (*Optional*): 设备名称.
- **default_properties** (*Required*): 要获取的属性值，以列表形式输入.
- **default_properties_getter** (*Required*): 对于 MiOT 设备，始终为 `get_properties`.
- **sensor_property** (*Required*): 以哪个属性作为传感器的状态. 其他属性作为 attribute.
- **sensor_unit** (*Optional*): 传感器单位.

Configuration variables (switch platform):
- **host** (*Required*): 设备 IP.
- **token** (*Required*): 设备 token.
- **name** (*Optional*): 设备名称.
- **turn_on_command** (*Optional*): 对于 MiOT 设备，始终为 `set_properties`.
- **turn_on_parameters** (*Optional*): 控制设备电源开的参数，以 json 形式输入.
- **turn_off_command** (*Optional*): 对于 MiOT 设备，始终为 `set_properties`.
- **turn_off_parameters** (*Optional*): 控制设备电源关的参数，以 json 形式输入.
- **state_property** (*Optional*): 获取设备电源状态的参数，以列表形式输入.
- **state_property_getter** (*Optional*): 对于 MiOT 设备，始终为 `get_properties`.
- **state_on_value** (*Optional*): 表示设备电源开的属性返回值，一般为 true.
- **state_off_value** (*Optional*): 表示设备电源关的属性返回值，一般为 false.

## 调试

如果组件工作不正常，通过修改配置文件提升日志调试级别:

```yaml
# configuration.yaml

logger:
  default: warn
  logs:
    custom_components.sensor.xiaomi_miot_raw: debug
    custom_components.switch.xiaomi_miot_raw: debug
    miio: debug
```

## Platform services

#### Service `xiaomi_miio_raw.sensor_set_properties`

Update the list of the retrieved properties.

| Service data attribute    | Optional | Description                                                                |
|---------------------------|----------|----------------------------------------------------------------------------|
| `entity_id`               |       no | Only act on a specific Xiaomi miIO fan entity.                             |
| `properties`              |      yes | List of properties. The default is `['power']`                             |


```
# http://localhost:8123/dev-service

Service: xiaomi_miio_raw.sensor_set_properties
Service Data: {"properties":["power","temperature","humidity","aqi"]}
```

#### Service `xiaomi_miio_raw.sensor_raw_command`

Send a command to the device.

| Service data attribute    | Optional | Description                                                                |
|---------------------------|----------|----------------------------------------------------------------------------|
| `entity_id`               |       no | Only act on a specific Xiaomi miIO fan entity.                             |
| `method`                  |       no | Method name of the command. Example: `set_power`                           |
| `params`                  |      yes | List of parameters. Example: `['on']`                                      |


```
# http://localhost:8123/dev-service

# Turn the device on
Service: xiaomi_miio_raw.sensor_raw_command
Service Data: {"method":"set_power","params":["on"]}

# Turn the device off
Service: xiaomi_miio_raw.sensor_raw_command
Service Data: {"method":"set_power","params":["off"]}

# Request some properties
Service: xiaomi_miio_raw.sensor_raw_command
Service Data: {"method":"get_prop","params":["power","temperature","humidity","aqi"]}
```

#### Service `xiaomi_miio_raw.sensor_turn_on`

Turn the device on.

| Service data attribute    | Optional | Description                                                          |
|---------------------------|----------|----------------------------------------------------------------------|
| `entity_id`               |       no | Only act on a specific xiaomi miio entity.                           |

#### Service `xiaomi_miio_raw.sensor_turn_off`

Turn the device off.

| Service data attribute    | Optional | Description                                                          |
|---------------------------|----------|----------------------------------------------------------------------|
| `entity_id`               |       no | Only act on a specific Xiaomi miIO fan entity.                       |

