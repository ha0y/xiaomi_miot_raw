各个设备类型公用的配置参数：
- **host** (*Required*): 设备 IP。
- **token** (*Required*): 设备 token。
- **name** (*Optional*): 设备名称。
- **mapping** (*Required*): 设备的功能与 id 的映射。
- **params** (*Optional*): 与 mapping 对应，指定关于属性值的一些信息。
- **scan_interval** (*Optional*): 状态刷新周期。

- **sensor_property** (*Required*，仅限 sensor): 把 mapping 中的哪一个作为传感器的状态。其他的将作为传感器的属性。
- **sensor_unit** (*Optional*，仅限 senso): 传感器单位。

- **update_from_cloud** 从米家服务器读取设备状态。

**mapping** 和 **params** 中的项目具有对应关系。params 是为了指定关于属性值的一些信息。比如说对于 switch_status，它代表开关状态，这一点是确定的；可是有的设备，值为 1 为开，值为 2 为关；有的设备值为 True 为开，值为 False 为关。这就需要在 params 中指定具体的状态值了。又如，蓝牙网关插座，显示的功率数值没有小数点，实际功率要除以 100；而某品牌插座，同样没有小数点，可实际功率要除以 10……这种问题同样可以在 params 中解决。二者的一些选项：

- **switch_status** (*Required* 适用于 light switch fan): 插件通过读写这个属性来获取和控制开关状态。其下的 **power_on** 和 **power_off** 指定开和关的状态值。
- **motor_control** (*Required* 适用于 cover)，插件通过读写这个属性来控制电机状态。其下的 **open**、**close** 和 **stop** 指定升/降/停的状态值。
- **motor_status** (*Optional* 适用于 cover)，插件通过读写这个属性来获取电机状态。其下的 **open**、**close** 和 **stop** 指定升/降/停的状态值。注意这些值可能与上面的控制值不同。
- **brightness** (*Optional* 适用于 light)：设置此项后支持亮度调节。
- **color_temperature** (*Optional* 适用于 light)：设置此项后支持色温调节。
- **oscillate** (*Optional* 适用于 fan)：设置此项后支持摇头。
- **speed** (*Optional* 适用于 fan)：设置此项后支持风速调节。
- **mode** (*Optional* 适用于 light fan)：灯、加湿器等设备的运行模式。
