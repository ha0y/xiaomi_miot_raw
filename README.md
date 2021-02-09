# Xiaomi MIoT Raw

[简体中文](https://github.com/ha0y/xiaomi_miot_raw/blob/add-miot-support/README_cn.md) | English
> 应 HACS 要求，临时修改默认 README 语言为英语。[点击此处查看中文说明](https://github.com/ha0y/xiaomi_miot_raw/blob/add-miot-support/README_cn.md)。

This custom component implements the Xiaomi MIoT protocol with the help of [python-miio](https://github.com/rytilahti/python-miio), and the usage is similar to [xiaomi_raw](https://github.com/syssi/xiaomi_raw).

Currently this custom component supports:
* sensor (get properties from device)
* switch (set binary properties to device)
* cover (supports open/close/set position, get position is not supported yet)
* light (turn on/off, adjust brightness and color temprature)
* fan (turn on/off, set oscillation and speed)
* humidifier (turn on/off, set target humidity and mode)
* media player (Xiaomi AI Speaker)

## Install

* Copy the custom_component folder to your Home Assistant configuration folder

or
* Add this repo ([https://github.com/ha0y/xiaomi_miot_raw](https://github.com/ha0y/xiaomi_miot_raw)) to [HACS](https://hacs.xyz/), then add "Xiaomi MiOT Raw"


## Configuration file

**Please refer to the [config_example folder](https://github.com/ha0y/xiaomi_miot_raw/tree/add-miot-support/config_example)**

Configuration variables common to each device type:
- **host** (*Required*): Device IP.
- **token** (*Required*): Device token.
- **name** (*Optional*): Device name.
- **mapping** (*Required*): The mapping between the function of the device and the id(siid, piid).
- **params** (*Optional*): For devices that can be controlled, specify the mapping between their functional status (such as on/off/up/down/stop) and value.
- **scan_interval** (*Optional*): Status refresh interval.

### For sensor:
- **sensor_property** (*Required*): The property in mapping that provides the current state. The rest will be the attributes of the sensor.
- **sensor_unit** (*Optional*): The sensor unit.

### For switch:
Required for **mapping** and **params**:

- **switch_status**, to obtain and control the switch status by reading and writing this attribute. The **power_on** and **power_off** below specify the on and off state values.

### For cover:
Required for **mapping** and **params**:

- **motor_control**, to obtain and control the motor state by reading and writing this attribute. The **open**, **close** and **stop** below specify the status value of up/down/stop.

### For light:
Required for **mapping** and **params**:
- **switch_status**, to obtain and control the light switch status by reading and writing this attribute. The **power_on** and **power_off** below specify the on and off state values.

Optional:
- **brightness**: After setting this option, will support brightness adjustment.
- **color_temperature**: After setting this option, will support color temperature adjustment.

### For fan:
Required for **mapping** and **params**:
- **switch_status**, to obtain and control the fan switch status by reading and writing this attribute. The **power_on** and **power_off** below specify the on and off state values.

Optional:
- **oscillate**: After setting this option, will support oscillation adjustment.
- **speed**: After setting this option, will support speed adjustment.

## Update log

### February 9
1. Support the sensor to automatically add units.
2. Add Xiao Ai "Broadcast designated text" and "Execute designated instructions" services.

### February 8
1. Support Xiaoai speaker configuration from UI.
2. Support action calls for devices e.g. washing machines.

### February 6
1. Support Xiaoai speakers.

### February 3
1. Supports multiple types of automatic configuration for one device. Now devices with sub-devices such as fan-lights and airers can be integrated in one time automatically.
2. Due to the reason of 1, the internal data storage method has undergone major changes. **Some devices need to be deleted and reconfigured, and the devices that need to be reconfigured have been stated in the notification bar**; the file-configured devices are not affected.
3. Greatly improve the accuracy of automatic identification.

### January 31
1. **Now supports automatic configuration of some device types. **
2. Fix a lot of bugs.
3. **Support humidifier. **

### January 28
1. Support UI configuration.

### January 26
1. Support RGB light.

### January 23
1. Support updating states from Mi Home cloud server for alternative. (Only Mainland China server is tested)
2. Support fan platform.

### January 18
1. Make the log more detailed.

### January 13
1. **Support light platform, now you can connect to smart lights, and adjust the light and color! **

### January 12
1. The method of value decimal is changed to the configuration item `value_ratio` under `params`.
2. Refactor the code, greatly optimize the code structure, and prepare for the expansion of device types.
3. **After this update, some entities related to this plug-in will be regenerated, with the suffix `_2`, and the original entity is no longer available. Please delete the previous entity, and then modify the entity ID of the new entity to remove `_2`. The history and original functions will not be affected. **
4. For switch entity that does not support state feedback, create an entity with assumed state.

### January 11
1. Now the switch can also display the attribute value of the device in the state attribute just like the sensor. This type of device does not need to configure the sensor, and can directly merge the mapping content of the previous sensor configuration.
2. ~~For some property values does not have a decimal point, a mapping of "power_100" is designed to correct the value.~~

### January 6
1. Support cover platform, now you can access curtains, drying racks and other devices
2. **In order to unify the configuration file format of multiple devices and facilitate the later expansion of more types of devices, major adjustments have been made to the configuration file format. The new version is no longer compatible with the previous format. Please pay attention to adaptation when upgrading **
3. Optimize the code structure and calling method


## Debug
If the custom component doesn't work out of the box for your device please update your configuration to increase log level:
```yaml
# configuration.yaml

logger:
  default: warn
  logs:
    custom_components.xiaomi_miot_raw: debug
    miio: debug
```