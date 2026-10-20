# 板载日志取数与软件端交接

本文面向负责数据与软件接入的成员，说明如何从 ESP32 板载 LittleFS 下载原始日志、生成 CSV、检查数据完整性并交付分析。本文不包含 Python、IDE 或驱动的入门安装说明。

## 1. 工具与入口

请使用仓库的 `hardware` 分支。取数链路涉及：

```text
collector/list_ports.py              列出串口
collector/download_flash_log.py      下载板载 JSONL 并转换为 CSV
src/rlls_demo/flash_log.py           日志协议解析与 CSV 转换
scripts/download_flash_log.cmd       Windows 交互式入口
requirements-collector.txt           最小依赖，仅 pyserial
```

`scripts/setup_collector.cmd` 只是可选的独立环境初始化脚本，不属于数据协议。已有可用 Python 环境时，安装 `requirements-collector.txt` 后即可直接调用下载器。

## 2. 连接电脑前的供电约束

取数时必须先关闭太阳能管理模块输出，并断开其到 ESP32 的 5 V/USB 输出，再连接电脑 USB。不要让两个电源同时给开发板供电。

同时关闭 Arduino Serial Monitor 和其他占用同一 COM 口的软件。USB 连接可能使 ESP32 重启并产生新的 `boot_id`，但不会自动删除已写入 Flash 的旧日志。

## 3. 确认串口

在仓库根目录执行：

```powershell
python collector\list_ports.py
```

若使用项目内环境：

```powershell
.\.venv-collector\Scripts\python.exe collector\list_ports.py
```

记录 ESP32 对应的端口，例如 `COM3`。若没有端口，先在设备管理器确认 USB 数据线、USB 转串口芯片和驱动状态。

## 4. 下载板载日志

命令行方式：

```powershell
python collector\download_flash_log.py `
  --port COM3 `
  --name field_20261020_01 `
  --timeout 300
```

也可以运行：

```text
scripts\download_flash_log.cmd
```

交互脚本会要求确认太阳能输出已断开，然后选择 COM 端口和输出名称。下载器发送 `LOG DUMP`，只接受固件输出的开始/结束标记之间的数据，并校验 JSON、必需字段及记录数量。下载过程不会清空板载日志。

成功后在 `data/live` 生成：

```text
field_20261020_01.jsonl
field_20261020_01.csv
```

- JSONL 是从设备取回的原始记录副本，应只读保存。
- CSV 是规范化后的分析与 Streamlit 回放文件。
- `data/live` 中的实测文件已被 Git 忽略，不会随代码提交到仓库。
- 输出文件已存在时下载器会拒绝覆盖，应使用新的批次名。

## 5. 串口协议

正式固件支持以下命令，Serial Monitor 或程序端均需以换行结尾发送：

```text
LOG STATUS   查询挂载、开关、文件大小和容量状态
LOG DUMP     下载日志
LOG ON       启用后续板载写入
LOG OFF      停止后续板载写入，不删除已有记录
LOG CLEAR    删除板载日志，必须在完成验证和备份后执行
```

自动下载器使用 `LOG DUMP`。不要依赖普通每秒实时输出判断下载边界；应以固件的 dump 开始、结束或错误标记为准。

## 6. 时间字段语义

当前硬件没有 RTC，太阳能离线运行时也没有可靠联网校时，因此不能为历史记录还原真实 UTC。数据字段含义如下：

- `boot_id`：一次启动会话的标识；设备重启后变化。
- `device_ms`：本次启动以来的毫秒数；重启后从零开始。
- `timestamp_utc`：离线日志中留空，不允许猜测或回填为下载时间。
- `timestamp_source`：离线记录为 `unavailable_no_rtc`。
- `downloaded_at_utc`：电脑实际下载该批日志的 UTC 时间，仅表示下载时间。

单个 `boot_id` 内可按 `device_ms` 排序。跨 `boot_id` 只能识别不同启动段，无法准确恢复两次启动之间的断电时长。

## 7. 数据验收

每批下载后至少检查：

1. JSONL 和 CSV 同时存在且非空。
2. CSV 至少有一条记录，且可以重新读取。
3. `simulated` 为 `false`。
4. 四路 `soil_*_raw` 没有长期全部固定为 0 或 4095。
5. 缺失值保持为空，不得用 0 代替。
6. `boot_id` 与 `device_ms` 的分段和顺序合理。
7. `soil_*_status` 与原始值一致；水端校准值为 0 时，ADC=0 仍需结合接线判断，不能仅凭百分比认定为 100% 湿润。

执行项目的数据契约检查：

```powershell
python scripts\validate_csv_contract.py data\live\field_20261020_01.csv
```

为交付文件记录 SHA256：

```powershell
Get-FileHash .\data\live\field_20261020_01.jsonl -Algorithm SHA256
Get-FileHash .\data\live\field_20261020_01.csv -Algorithm SHA256
```

JSONL、CSV、两个哈希值及本次取数记录应一起保存。不要用 Excel 覆盖原始 JSONL。

## 8. Streamlit 回放

启动页面后选择“CSV 回放”，上传或选择刚生成的 CSV。对于没有 `timestamp_utc` 的板载日志，页面使用 `boot_id + device_ms` 展示相对顺序，不会把下载时间冒充采样时间。

如果页面提示模型为 `MockModel`，该结果仅用于验证软件链路，不代表真实农业模型输出。

## 9. 常见错误

### 找不到串口

确认 USB 线支持数据，检查设备管理器和 USB 转串口驱动，重新插拔后再次运行端口枚举工具。

### 端口拒绝访问或被占用

关闭 Serial Monitor、Arduino IDE 和其他串口程序。同一个 COM 口同一时刻只能由一个进程占用。

### `storage_not_mounted`

停止清空或重新烧录操作，保留错误输出，核对正式固件与 Arduino IDE 的 Partition Scheme。

### 日志为空

先执行 `LOG STATUS`，确认本地日志开启、已有运行时间且空间未满。不要为了测试下载而伪造记录。

### 只得到 JSONL，没有 CSV

保留 JSONL，不要清空设备。检查报错所指的 JSON 行、字段或 schema 版本，修复转换问题后重新用新文件名下载。

### 下载超时

大日志可提高 `--timeout`。若串口中断，保留已生成文件但不要把未通过校验的 CSV 作为正式数据；重新连接后使用新批次名重试。

## 10. 清空策略

只有同时满足以下条件后，才允许发送 `LOG CLEAR`：

- JSONL 和 CSV 均已通过检查；
- 文件至少保存到两个独立位置；
- SHA256 已记录；
- 软件端已成功读取 CSV；
- 项目负责人确认该批数据不再需要留在 ESP32 上。

清空前后分别执行 `LOG STATUS` 并保存输出。清空是不可恢复操作。

## 11. 交接记录模板

```text
批次名称：
设备/板号：
取数人员：
下载时间（UTC/本地）：
COM 端口：
CSV 记录数：
boot_id 数量：
JSONL SHA256：
CSV SHA256：
原始文件备份位置 1：
原始文件备份位置 2：
是否执行 LOG CLEAR：否 / 是（批准人：）
异常与备注：
```
