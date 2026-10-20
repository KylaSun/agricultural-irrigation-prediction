# 太阳能供电版：接线、烧录、采集与数据确认

本文对应当前硬件：6 V / 6 W 太阳能板、单节 3.7 V 18650、DFRobot 5 V 太阳能充电稳压模块、ESP32-DevKitC V4 / ESP32-WROOM-32、四支 DFRobot SEN0308。

## 1. 当前已确认的软件配置

四路信号映射：

```text
soil_01 黄线 → GPIO32
soil_02 黄线 → GPIO33
soil_03 黄线 → GPIO34
soil_04 黄线 → GPIO26
```

正式固件：

```text
firmware/esp32_irrigation_demo/esp32_irrigation_demo.ino
```

快速校准固件：

```text
firmware/esp32_soil_calibration/esp32_soil_calibration.ino
```

正式固件已设置 `USE_SIMULATED_VALUES=false`，并写入 2026-10-18 的暂定实测端点：

```cpp
static const int DRY_RAW[PROBE_COUNT] = {1907, 959, 408, 740};
static const int WET_RAW[PROBE_COUNT] = {0, 0, 0, 0};
```

湿端 0 来自 DFRobot 的水端校准方法。干端差异较大，必须在最终供电、固定插入深度和约定土壤条件下复测；当前百分比只能称为两点标定后的相对指标，不是真实体积含水率。

## 2. 接线前必须确认

### 2.1 确认太阳能管理模块

根据描述，模块可能是 DFRobot Solar Power Manager 5V（DFR0559），但必须查看 PCB、包装或订单确认精确 SKU 和硬件版本。只有当实物端子和对应官方说明一致时，才按本文连接。

- DFR0559 官方说明：<https://wiki.dfrobot.com/dfr0559>
- SEN0308 官方说明：<https://wiki.dfrobot.com/sen0308>

若板上没有清晰的 `SOLAR IN`、`BAT IN`、`5V/USB OUT` 或端子极性与本文不同，停止接线，不要按名称猜测。

### 2.2 安全条件

- 18650 必须是单节标称 3.7 V 锂电池；检查外皮、正负极、容量和保护类型。
- 不使用破损、鼓包、漏液、来源不明或极性不清的电芯。
- 不让裸露电池正负极接触金属工具；不要在不具备条件时直接焊接裸电芯。
- 太阳能板标称 6 V 不代表开路电压一定是 6 V。接入前核对面板资料和管理模块对应版本的允许输入范围。
- DFRobot 对 5 W 及以上面板建议为管理芯片安装配套导热垫和散热片；6 W 面板按该要求处理。
- 模块稳压 5 V 不能接 ESP32 的 `3V3` 或任何 GPIO。
- 烧录和电脑采集期间，不让电脑 USB 与模块 5 V 同时给 ESP32 供电。

## 3. 新增供电部分接线

所有接线操作均先断开电脑 USB、太阳能板和电池。逐步连接，每一步确认极性后再进行下一步。

### 3.1 电源链路

```text
6 V / 6 W 太阳能板
        │
        ▼
太阳能管理模块 SOLAR IN
        │
        ├── BAT IN ↔ 单节 3.7 V 18650
        │
        └── 稳压 5V/USB OUT → ESP32 5V/VIN 或 ESP32 USB 供电口
```

顺序：

1. 将模块输出开关或 ON/OFF 跳线置于关闭状态。
2. 按模块实物极性将 18650 电池座连接到 `BAT IN`。
3. 按模块实物极性将太阳能板连接到 `SOLAR IN`。
4. 暂时不要把模块输出接入 ESP32；先按模块指示灯说明确认没有反接或异常发热。
5. 需要太阳能独立运行时，在电脑 USB 已拔除的前提下，将模块稳压 `5V/USB OUT` 接到 ESP32 的 `5V/VIN` 与 GND，或者使用模块 USB OUT 给 ESP32 USB 口供电。两种输出方式二选一。
6. 打开模块输出，并确认 ESP32 正常启动、没有反复复位、异味或异常发热。

### 3.2 四支探头

SEN0308 仍由 ESP32 的 3.3 V 供电，以保持与当前校准条件一致：

```text
四支红线       → ESP32 3V3
四支黄线       → GPIO32 / GPIO33 / GPIO34 / GPIO26
每支两根黑线   → ESP32 GND
```

不要把 SEN0308 红线改接到太阳能模块 5 V 后继续沿用当前校准值。供电电压发生变化时必须重新校准。

面包板主孔区同一编号的五孔组内部相通，中间沟槽两侧不相通；长电源轨也可能在中间断开。黄色信号线不得与任一黑色 GND 线处于同一导电组。

## 4. 两种工作状态不能混用

### 状态 A：烧录和电脑串口采集

```text
电脑 USB → ESP32
太阳能管理模块 5 V 输出 → 与 ESP32 断开
```

该状态用于上传固件、查看 Serial Monitor、运行 Python collector 和 Streamlit。太阳能板与电池可以留在管理模块一侧，但模块输出不能接 ESP32。

### 状态 B：太阳能独立供电

```text
电脑 USB → 拔除
太阳能管理模块稳压 5 V → ESP32
```

该状态用于验证太阳能/电池能否让 ESP32 独立运行。正式固件会每 60 秒把一条记录保存到 ESP32 板载 LittleFS；断开电脑 USB 后不会实时写入电脑 CSV，但之后可以重新通过 USB 下载。完整步骤见 `docs/LOCAL_FLASH_LOG_CN.md`。

若后续必须同时太阳能供电和连接电脑数据，应增加经过验证的电源隔离或独立 UART 方案，并单独评审；不要把两路 5 V 直接并联。

## 5. 烧录正式程序

1. 断开太阳能管理模块到 ESP32 的 5 V 输出。
2. 使用支持数据的 USB 线将 ESP32 接到电脑。
3. 在 Arduino IDE 打开：

   ```text
   D:\Codex Program\RLLS\firmware\esp32_irrigation_demo\esp32_irrigation_demo.ino
   ```

4. 检查关键配置：

   ```cpp
   static const bool USE_SIMULATED_VALUES = false;
   static const int SOIL_PINS[PROBE_COUNT] = {32, 33, 34, 26};
   static const int DRY_RAW[PROBE_COUNT] = {1907, 959, 408, 740};
   static const int WET_RAW[PROBE_COUNT] = {0, 0, 0, 0};
   ```

5. 选择实际 ESP32 board 和 COM 端口，点击 Upload。
6. 上传过程中如果卡在 Connecting，暂时拆除所有外设信号线，只保留 USB，必要时按住 BOOT 后开始上传。
7. 上传完成后打开 Serial Monitor，波特率设为 `115200`。
8. 正式程序应每秒输出一个 JSON 对象，不应出现校准菜单或普通调试文本。
9. 在 Serial Monitor 输入 `LOG STATUS`，确认返回 `mounted=1 enabled=1`；控制响应以 `#RLLS_` 开头，不属于传感器数据。

示例结构：

```json
{"schema_version":"2.0.0-demo","device_ms":1000,"soil_1_raw":1800,"soil_1_moisture_pct":5.61,"soil_1_status":"ok","soil_2_raw":900,"soil_2_moisture_pct":6.15,"soil_2_status":"ok","soil_3_raw":390,"soil_3_moisture_pct":4.41,"soil_3_status":"ok","soil_4_raw":700,"soil_4_moisture_pct":5.41,"soil_4_status":"ok","simulated":false}
```

以上数字只是格式示例，不是期望现场读数。

## 6. Python 串口采集

采集前关闭 Arduino Serial Monitor，因为同一个 COM 端口不能同时被两个程序占用。

在 PowerShell 中：

```powershell
cd "D:\Codex Program\RLLS"
.\.venv\Scripts\python.exe collector\list_ports.py
```

记下 ESP32 对应端口，例如 `COM3`，然后运行：

```powershell
.\.venv\Scripts\python.exe collector\serial_collector.py `
  --port COM3 `
  --baud 115200 `
  --output data\live\sensor_readings.csv `
  --mode c1_soil_only `
  --active-probe soil_composite
```

端口不是 COM3 时必须替换。按 `Ctrl+C` 可停止采集；已写入 CSV 的记录会保留。

## 7. 打开 Streamlit

另开一个 PowerShell 窗口：

```powershell
cd "D:\Codex Program\RLLS"
.\.venv\Scripts\python.exe -m streamlit run app\streamlit_app.py
```

页面中选择：

```text
数据来源 → 实时串口 CSV
实时 CSV 路径 → data\live\sensor_readings.csv
模型土壤湿度来源 → 四探头综合值（有效值中位数）
```

Streamlit 不直接打开串口，只读取 collector 持续追加的 CSV，因此刷新页面不会重复占用 COM 端口。

## 8. 数据验收

至少连续采集 5 分钟并检查：

- 每秒大致新增一条记录，`timestamp_utc` 为电脑接收时间。
- `simulated` 必须为 `false`。
- 四个 `soil_n_status` 正常情况下均为 `ok`。
- 四个 raw 在稳定环境中不应长期随机跳到边界；水端出现 0 可以是当前校准定义，不能简单当作缺失。
- `status="ok"` 只表示程序成功取得 ADC 数值并完成换算，不证明探头物理连接一定正常。由于本次水端本身是 0，现场持续为 0 也可能是信号短接或断线；必须结合环境、其他探头和人工接线检查判断。
- CSV 中缺失值为空，不使用数字 0 表示“没接、超时或关闭”。
- `soil_composite_pct` 至少由两支有效探头的中位数生成。
- 改变一支探头环境时，对应 raw 和相对百分比应按预期变化，其他通道不应同步大幅跳变。
- 断开一支探头时，系统应通过状态与质量提示暴露问题，而不是把它当作真实 0% 湿度。

可运行仓库验证：

```powershell
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe scripts\self_check.py
.\.venv\Scripts\python.exe scripts\validate_csv_contract.py data\live\sensor_readings.csv
```

## 9. 太阳能独立运行验收

完成电脑采集验证后再切换：

1. 停止 collector，关闭 Serial Monitor。
2. 拔掉电脑 USB。
3. 接通管理模块稳压 5 V 到 ESP32。
4. 打开模块输出，观察 ESP32 电源灯和复位行为。
5. 分别在有光、遮挡面板和仅电池条件下记录启动情况与持续运行时间。

当前没有电池电压/电量遥测，因此不能仅凭 ESP32 仍在运行就宣称续航或充电效率。续航、阴天稳定性和供电切换结果必须使用测试记录和明确测量工具获得。

独立运行结束后，先关闭太阳能模块输出并断开其 5 V，再接电脑 USB。使用以下命令下载板载记录：

```powershell
.\.venv\Scripts\python.exe collector\download_flash_log.py --port COM3
```

端口按实际替换。下载不会自动清空 ESP32；确认 JSONL 和 CSV 均完整后，才可按 `docs/LOCAL_FLASH_LOG_CN.md` 执行 `LOG CLEAR`。当前没有 RTC，离线 CSV 的测量 UTC 为空，使用 `boot_id + device_ms` 表示启动分段和段内顺序。

## 10. 仍需回填的信息

- DFRobot 太阳能管理模块精确 SKU 和硬件版本。
- 6 V / 6 W 面板精确型号及开路电压。
- 18650 品牌、容量、最大充电电流和保护类型。
- 最终供电拓扑照片和端子极性记录。
- 四支探头在最终供电、相同介质、固定深度下的重复校准结果。
- 是否需要太阳能供电期间继续向电脑或网络发送数据；若需要，需新增通信与电源隔离设计。
