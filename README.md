# Xiaomi MIoT Raw

简体中文 | [English](https://github.com/ha0y/xiaomi_miot_raw/blob/add-miot-support/README_en.md)

>**1 月 23 日更新**  
>**支持从米家服务器读取状态，以解决部分设备通过局域网读取时出现 -9999 或 -4004 错误的问题！**

MIoT 协议是小米智能家居从 2018 年起推行的智能设备通信协议规范，此后凡是可接入米家的设备均通过此协议进行通信。此插件按照 MIoT 协议规范，通过局域网直接与设备通信，实现对设备的状态读取及控制。由于 MIoT 协议具有极强的通用性，一些功能简单的智能设备就可以通过此插件快速高效地接入 Home Assistant，而不必再拘泥于设备型号、不必再等待别人去写插件适配了。

目前此插件已支持以下设备类型：
* sensor (传感器，一次性读取设备的多个状态)
* switch (开关，使设备的某个功能在两个指定状态之间切换，并支持读取设备正处于哪个状态，在设备状态变化时自动刷新)
* cover (卷帘，用于接入晾衣架、升降帘、窗帘等具有升降或开合功能的设备，目前支持的操作有：升降停、设置指定位置，**现已支持状态反馈，并支持从米家服务器读取状态！**)
* light (灯，可以开关、调亮度、调色、设置灯效)

如果对您有帮助，欢迎给个 Star！ 🌟 

## 安装

* 将 custom_component 文件夹中的内容拷贝至自己的相应目录

或者
* 将此 repo ([https://github.com/ha0y/xiaomi_miot_raw](https://github.com/ha0y/xiaomi_miot_raw)) 添加到 [HACS](https://hacs.xyz/)，然后添加“Xiaomi MiOT Raw”


## 配置文件


**请参考 [config_example 文件夹](https://github.com/ha0y/xiaomi_miot_raw/tree/add-miot-support/config_example)** 内的相关文件

各个设备类型公用的配置参数：
- **host** (*Required*): 设备 IP。
- **token** (*Required*): 设备 token。
- **name** (*Optional*): 设备名称。
- **mapping** (*Required*): 设备的功能与 id 的映射。
- **params** (*Optional*): 对于可以控制的设备，指定其功能状态（如：开/关/升/降/停）与 value 的映射。
- **scan_interval** (*Optional*): 状态刷新周期。

### 针对 sensor：
- **sensor_property** (*Required*): 把 mapping 中的哪一个作为传感器的状态。其他的将作为传感器的属性。
- **sensor_unit** (*Optional*): 传感器单位。

### 针对 switch：
该设备类型的 **mapping** 和 **params** 下必须有以下条目：

- **switch_status**，插件通过读写这个属性来获取和控制开关状态。其下的 **power_on** 和 **power_off** 指定开和关的状态值。

### 针对 cover：
该设备类型的 **mapping** 和 **params** 下必须有以下条目：

- **motor_control**，插件通过读写这个属性来控制电机状态。其下的 **open**、**close** 和 **stop** 指定升/降/停的状态值。

可以有以下条目：

- **motor_status**，插件通过读写这个属性来获取电机状态。其下的 **open**、**close** 和 **stop** 指定升/降/停的状态值。注意这些值可能与上面的控制值不同。

该设备类型的 **update_from_cloud** 使插件可以从米家服务器读取设备状态，解决邦先生等设备禁止从局域网读取的问题。具体配置请参考样例文件。

### 针对 light：
该设备类型的 **mapping** 和 **params** 下必须有以下条目：
- **switch_status**，插件通过读写这个属性来获取和控制灯开关状态。其下的 **power_on** 和 **power_off** 指定开和关的状态值。

可以有以下条目：
- **brightness**：设置此项后支持亮度调节。
- **color_temperature**：设置此项后支持色温调节。


## 更新日志
### 1 月 23 日
1. **支持从米家服务器读取状态，以解决部分设备通过局域网读取时出现 -9999 或 -4004 错误的问题！**

### 1 月 18 日
1. 使调试日志内容更加详细，方便排查问题。

### 1 月 13 日
1. **支持 light 设备类型，可以接入智能灯，并调光调色了！**
2. 支持灯内置的场景色选择

### 1 月 12 日
1. 数值修正的方法变更为 `params` 下 `value_ratio` 配置项。
2. 重构代码，大幅优化代码结构，为扩展设备类型做准备。
3. **本次更新后，涉及本插件的部分实体会重新生成，其 ID 带有后缀 `_2`，原实体不再可用。请删除之前的实体，然后把新实体的实体 ID 修改去除 `_2` 即可，历史记录和原有功能不受影响。**
4. 开关类型的实体在检测到不支持状态反馈后，会创建无状态反馈的实体用于控制。

### 1 月 11 日
1. 现在 switch 也可以像 sensor 一样把设备的属性值显示在 state attribute 中了。此类设备无需再配置 sensor，直接将以前 sensor 配置的 mapping 内容合并进来即可，减少一半的网络请求。
2. ~~针对“小米智能插座2 蓝牙网关版”的功率没有小数点的问题，设计了一个“power_100”的 mapping 对数值进行修正。~~

### 1 月 6 日
1. 支持 cover 设备类型，现在可以接入窗帘、晾衣架等设备了
2. **为了使多种设备的配置文件格式统一、方便后期拓展更多类型的设备，对配置文件格式进行了较大调整，新版本不再兼容以前的格式，请在升级时注意适配**
3. 优化代码结构及调用方式，响应更快了


## 调试
如果组件工作不正常，通过修改配置文件提升日志调试级别:
```yaml
# configuration.yaml

logger:
  default: warn
  logs:
    custom_components.xiaomi_miot_raw: debug
    miio: debug
```
