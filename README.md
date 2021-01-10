# Xiaomi MIoT Raw

MIoT 协议是小米智能家居从 2018 年起推行的智能设备通信协议规范，此后凡是可接入米家的设备均通过此协议进行通信。此插件按照 MIoT 协议规范，通过局域网直接与设备通信，实现对设备的状态读取及控制。由于 MIoT 协议具有极强的通用性，一些功能简单的智能设备就可以通过此插件快速高效地接入 Home Assistant，而不必再拘泥于设备型号、不必再等待别人去写插件适配了。

目前此插件以支持以下设备类型：
* sensor (通用传感器，一次性读取设备的多个状态)
* switch (通用开关，使设备的某个功能在两个指定状态之间切换，并支持读取设备正处于哪个状态，在设备状态变化时自动刷新)
* cover (通用卷帘，用于接入晾衣架、升降帘、窗帘等具有升降或开合功能的设备，目前支持的操作有：升降停、设置指定位置，暂不支持状态反馈，后期会支持)

本插件的 sensor 和 switch 部分修改自 [syssi](https://github.com/syssi) 的 [xiaomi_raw](https://github.com/syssi/xiaomi_raw)，cover 部分参考了 [Natic](https://github.com/tiandeyu) 的 [dooya_curtain](https://github.com/tiandeyu/dooya_curtain)，在此表示感谢！

如果对您有帮助，欢迎给个 Star！ 🌟 

## 安装

* 将 custom_component 文件夹中的内容拷贝至自己的相应目录

或者
* 将此 repo ([https://github.com/ha0y/xiaomi_miot_raw](https://github.com/ha0y/xiaomi_miot_raw)) 添加到 [HACS](https://hacs.xyz/)，然后添加“Xiaomi MiOT Raw”


## 配置文件

```yaml
请参考 config_example.yaml

```
各个设备类型公用的配置参数：
- **host** (*Required*): 设备 IP。
- **token** (*Required*): 设备 token。
- **name** (*Optional*): 设备名称。
- **mapping** (*Required*): 设备的功能与 id 的映射。
- **params** (*Optional*): 对于可以控制的设备，指定其功能状态（如：开/关/升/降/停）与 value 的映射。

### 针对 sensor：
- **sensor_property** (*Required*): 把 mapping 中的哪一个作为传感器的状态。其他的将作为传感器的属性。
- **sensor_unit** (*Optional*): 传感器单位。
- **scan_interval** (*Optional*): 刷新周期。

### 针对 switch：
该设备类型的 **mapping** 下必须有一个 **switch_status**，插件通过读写这个属性来获取和控制开关状态。

该设备类型要的 **params** 下也必须有一个 **switch_status**，用于指定开/关的状态值。

### 针对 cover：
该设备类型的 **mapping** 下必须有一个 **motor_control**，插件通过读写这个属性来获取和控制电机状态。

该设备类型要的 **params** 下也必须有一个 **motor_control**，用于指定升/降/停的状态值。

## 调试

如果组件工作不正常，通过修改配置文件提升日志调试级别:

## 更新日志
### 1 月 11 日
1. 现在 switch 也可以像 sensor 一样把设备的属性值显示在 state attribute 中了。此类设备无需再配置 sensor，直接将以前 sensor 配置的 mapping 内容合并进来即可，减少一半的网络请求。
2. 针对“小米智能插座2 蓝牙网关版”的功率没有小数点的问题，设计了一个“power_100”的 mapping 对数值进行修正。

### 1 月 6 日
1. 支持 cover 设备类型，现在可以接入窗帘、晾衣架等设备了
2. **为了使多种设备的配置文件格式统一、方便后期拓展更多类型的设备，对配置文件格式进行了较大调整，新版本不再兼容以前的格式，请在升级时注意适配**
3. 优化代码结构及调用方式，响应更快了


```yaml
# configuration.yaml

logger:
  default: warn
  logs:
    custom_components.sensor.xiaomi_miot_raw: debug
    custom_components.switch.xiaomi_miot_raw: debug
    miio: debug
```
