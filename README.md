# RLLS 低成本灌溉硬件 Demo

这是独立的 `hardware` 分支，只保留低成本灌溉实物 Demo 所需的固件、串口采集、数据处理、模型接入接口、Streamlit 页面、示例数据、文档和测试。研究代码与分析 notebook 不包含在本分支中，本分支也不设计为直接合并回 `main`。

> 当前模拟数据和 `MockModel` 仅用于验证数据链路与界面，不代表真实传感器读数、模型性能或农业建议。

## 数据链路

6 V / 6 W 太阳能板 → DFRobot 5 V 太阳能充电稳压模块 ↔ 3.7 V 18650 → ESP32

四路土壤湿度探头 → ESP32 → USB/Serial（JSON Lines）→ Python/pyserial → CSV → 数据预处理 → ModelAdapter → Streamlit

太阳能链路只负责供电，当前没有电池电量、电压或充电电流遥测。PC 串口采集仍需要 USB 数据连接；为避免双电源倒灌，烧录和 PC 采集时应断开太阳能模块到 ESP32 的 5 V 输出。

## 主要目录

- `firmware/`：ESP32 四路采集与快速校准程序。
- `collector/`：串口采集和无硬件模拟采集。
- `config/`：数据字段、模式和模型配置。
- `src/rlls_demo/`：解析、校验、预处理与模型适配接口。
- `app/`：Streamlit Demo。
- `data/replay/`：明确标注的模拟回放数据。
- `docs/`：接线、校准、BOM、演示与测试文档。
- `tests/`：基础自动化测试。
- `scripts/`：Windows 启动脚本。

## 快速启动

在 PowerShell 中执行：

```powershell
cd "D:\Codex Program\RLLS"
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-demo.txt
.\.venv\Scripts\python.exe collector\serial_collector.py --simulate --max-records 120 --interval 0.1
.\.venv\Scripts\python.exe -m streamlit run app\streamlit_app.py
```

如果 PowerShell 禁止运行 `.ps1`，可直接使用上面的 Python 命令，不需要修改系统执行策略。

## ESP32 接入

1. 当前实物映射为 GPIO32、33、34、26；GPIO26 属于 ADC2，ESP32 端启用 Wi-Fi 前必须重新评估。
2. 正式固件已写入 2026-10-18 的暂定实验端点：干端 `{1907, 959, 408, 740}`，水端 `{0, 0, 0, 0}`；固定最终供电、土壤和插入深度后仍需复测。
3. 正式固件默认 `USE_SIMULATED_VALUES=false`，每秒输出一条四探头 JSONL。
4. 烧录后以 115200 波特率连接，采集程序通过 `--port COMx` 指定 Windows 串口。
5. 太阳能接线、供电切换、烧录、采集和验收全过程见 `docs/SOLAR_POWER_WORKFLOW_CN.md`。

详细说明见：

- `docs/SOLAR_POWER_WORKFLOW_CN.md`
- `docs/QUICK_CALIBRATION_CN.md`
- `docs/WIRING_TEMPLATE_CN.md`
- `docs/CSV_COMPATIBILITY_CN.md`
- `docs/DEPENDENCIES_CN.md`

## 当前边界

- 正式天气 API 尚待接口文档、鉴权方式、字段单位与更新频率确认。
- 正式模型尚需模型文件、精确特征契约、训练预处理、阈值和固定测试样例。
- 当前探头校准值来自一次实物测量，但尚未完成重复性、最终土壤、固定深度和最终供电条件验证，因此只能视为暂定实验校准。
- 当前水端校准值为 0，因此现场 ADC=0 既可能代表水端，也可能代表短接/断线；单靠模拟值无法自动区分，必须结合接线检查和重复测量。
- 太阳能充电模块精确 SKU、硬件版本、18650 容量及保护类型仍需从实物标签回填。
- 三种传感器模式会实际改变传给模型的字段；最终字段仍必须与对应模型训练契约一致。

## 验证

```powershell
.\.venv\Scripts\python.exe -m pytest
```
