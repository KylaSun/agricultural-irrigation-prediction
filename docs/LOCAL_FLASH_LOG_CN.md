# ESP32 板载日志：保存、下载与清空

正式固件现已支持把四支 SEN0308 的读数保存到 ESP32 板载 Flash 的 LittleFS 文件系统。该功能适合太阳能独立运行期间的 Demo/短期记录，之后再用 USB 接回电脑下载。

## 1. 当前行为

- USB 串口仍每秒输出一条实时 JSONL，现有 collector 不受影响。
- 板载日志默认开启，每 60 秒保存一条，文件名为 `/soil_log.jsonl`。
- 日志达到固件设定的安全上限后停止追加，不自动覆盖或删除旧数据。
- 每次启动写入一个 `boot_id` 分段标记；`device_ms` 是该次启动后的毫秒数。
- 当前没有 RTC。离线 CSV 的 `timestamp_utc` 必须为空，不能用 0 或下载时间冒充测量时间。
- 电脑下载不会自动删除 ESP32 内的副本。

关键设置位于：

```text
firmware/esp32_irrigation_demo/esp32_irrigation_demo.ino
```

```cpp
LOCAL_LOG_INTERVAL_MS = 60000
LOCAL_LOG_MAX_BYTES = 1 MiB
LOCAL_LOG_DEFAULT_ENABLED = true
```

实际可用空间还受 Arduino IDE 的 Partition Scheme 影响。若所选分区没有可用文件系统，串口状态会显示 `mounted=0`，固件仍可实时输出，但不会本地保存。

## 2. 烧录和首次确认

1. 先断开太阳能管理模块到 ESP32 的 5 V 输出。
2. 用电脑 USB 连接 ESP32。
3. 在 Arduino IDE 上传正式固件：

   ```text
   D:\Codex Program\RLLS\firmware\esp32_irrigation_demo\esp32_irrigation_demo.ino
   ```

4. 打开 Serial Monitor，波特率选择 `115200`。
5. 行尾选择 `Newline` 或 `Both NL & CR`，输入：

   ```text
   LOG STATUS
   ```

6. 看到类似下列响应即表示已挂载：

   ```text
   #RLLS_LOG_STATUS mounted=1 enabled=1 bytes=... limit_bytes=... interval_ms=60000 clock=unsynced
   ```

若 `mounted=0`，先核对 Arduino IDE 的 Partition Scheme 是否包含 SPIFFS/LittleFS 空间，再重新烧录。不要为了修复挂载而随意执行整片 Flash 擦除，因为这会删除已有日志和其他持久数据。

## 3. 太阳能离线记录

确认 `mounted=1 enabled=1` 后：

1. 关闭 Serial Monitor。
2. 拔掉电脑 USB。
3. 确认电脑 USB 已断开，再接通太阳能管理模块稳压 5 V 到 ESP32。
4. 让设备独立运行。
5. 不要同时让电脑 USB 和太阳能模块 5 V 给 ESP32 供电。

板载日志不依赖 Streamlit 或 Python 持续运行。断电前已关闭并写入的记录会保留；突然掉电时，正在写入的最后一条记录可能不完整，下载程序会明确报错，而不会静默接受损坏记录。

## 4. 接回电脑下载

先关闭太阳能模块输出，并断开它到 ESP32 的 5 V；然后再插电脑 USB。不要让两路 5 V 并联。

关闭 Arduino Serial Monitor，打开 PowerShell：

```powershell
cd "D:\Codex Program\RLLS"
.\.venv\Scripts\python.exe collector\list_ports.py
```

确认端口后下载，例如 ESP32 是 `COM3`：

```powershell
.\.venv\Scripts\python.exe collector\download_flash_log.py --port COM3
```

程序会在 `data\live\` 生成两份带 UTC 下载时间的文件：

```text
esp32_flash_log_YYYYMMDDTHHMMSSZ.jsonl
esp32_flash_log_YYYYMMDDTHHMMSSZ.csv
```

- JSONL 是原始板载日志副本，保留启动分段标记。
- CSV 便于查看和导入 Streamlit。
- `downloaded_at_utc` 只表示下载时间。
- `timestamp_utc` 为空，表示没有可靠的测量 UTC。
- 同一个 `boot_id` 内可按 `device_ms` 排序；不同 `boot_id` 代表设备曾重启，不能仅凭 `device_ms` 推算跨段真实时间。

下载大文件需要时间，默认最长等待 180 秒。不要在下载途中拔线；如确有需要可通过 `--timeout 300` 延长等待。

下载脚本拒绝覆盖同名文件。可用 `--name` 指定新名称：

```powershell
.\.venv\Scripts\python.exe collector\download_flash_log.py --port COM3 --name field_test_01
```

## 5. 在 Streamlit 查看

启动页面：

```powershell
.\.venv\Scripts\python.exe -m streamlit run app\streamlit_app.py
```

选择“CSV 回放”，上传刚下载的 CSV。因为没有 RTC，页面会显示时间无效/缺失，趋势图改用 `device_ms`；这是预期的数据质量提示，不应手工伪造 UTC 来消除提示。

## 6. 核对后再清空 ESP32

先确认以下内容：

- JSONL 和 CSV 两个文件都存在且非空。
- CSV 行数符合大致运行时长和 60 秒记录间隔。
- 四个 raw、百分比和状态字段可读。
- 将文件另外备份后再考虑清空。

清空属于不可恢复操作。确认无误后，在 Arduino Serial Monitor 输入：

```text
LOG CLEAR
```

看到 `#RLLS_LOG_CLEARED` 才表示成功。也可以使用：

```text
LOG OFF
LOG ON
LOG STATUS
LOG DUMP
```

`LOG OFF/ON` 只影响当前这次开机；重新启动后恢复固件默认设置。`LOG DUMP` 会把内容输出到串口，正式下载仍建议使用 Python 工具，以便校验记录并同时生成 JSONL/CSV。

## 7. 当前限制与后续升级

- Flash 有有限写入寿命，不能把本地间隔无评估地改成 1 秒长期运行。
- 容量由分区方案决定；长周期、高频采样应改用 microSD 或远程传输。
- 没有 RTC 时，断电重启后的真实采样时间不可恢复。若实验需要准确时间，建议增加带后备电池的 RTC，并把 RTC 型号、校时流程和时区写入数据契约。
- GPIO26 属于 ADC2；如果以后在 ESP32 上启用 Wi-Fi 上传数据，应先解决 ADC2 与 Wi-Fi 的冲突，不能直接沿用当前接线。
