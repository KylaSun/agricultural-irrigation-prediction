# 接线记录模板

## 基本信息

- 日期/记录人：
- ESP32 精确板型与版本：
- Pinout 链接/文件：
- USB-UART 芯片：
- 供电电压与电源：
- Arduino board package 版本：

## 已确定的四路接线

| 传感器 | 精确型号 | 信号类型 | 传感器引脚 | ESP32 GPIO | 供电 | 共地 | 是否需要分压/上拉 | 已核对 ADC/启动脚限制 |
|---|---|---|---|---|---|---|---|---|
| soil_01 | DFRobot SEN0308 | Analog | 黄=Signal；红=VCC；黑×2=GND | GPIO32 | 3V3 | 是 | 否 | ADC1，待实板复核 |
| soil_02 | DFRobot SEN0308 | Analog | 黄=Signal；红=VCC；黑×2=GND | GPIO33 | 3V3 | 是 | 否 | ADC1，待实板复核 |
| soil_03 | DFRobot SEN0308 | Analog | 黄=Signal；红=VCC；黑×2=GND | GPIO34 | 3V3 | 是 | 否 | ADC1、仅输入，待实板复核 |
| soil_04 | DFRobot SEN0308 | Analog | 黄=Signal；红=VCC；黑×2=GND | GPIO35 | 3V3 | 是 | 否 | ADC1、仅输入，待实板复核 |

## 上电前检查

- [ ] 查阅到货 ESP32-DevKitC V4 pinout，并核对 GPIO32/33/34/35 丝印
- [ ] 传感器输出不超过 ESP32 输入允许电压
- [ ] ADC 引脚与 Wi-Fi/启动功能冲突已评估
- [ ] 所有模块共地
- [ ] 裸露电极与水远离 USB/电脑
- [ ] 先单传感器测试，再组合接线

## 修改记录

| 时间 | 修改 | 原因 | 结果 |
|---|---|---|---|
|  |  |  |  |
