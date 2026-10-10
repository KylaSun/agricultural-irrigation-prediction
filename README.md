# RLLS 低成本灌溉硬件 Demo

这是独立的 `hardware` 分支，只保留低成本灌溉实物 Demo 所需的固件、串口采集、数据处理、模型接入接口、Streamlit 页面、示例数据、文档和测试。研究代码与分析 notebook 不包含在本分支中，本分支也不设计为直接合并回 `main`。

> 当前模拟数据和 `MockModel` 仅用于验证数据链路与界面，不代表真实传感器读数、模型性能或农业建议。

## 数据链路

四路土壤湿度探头 → ESP32 → USB/Serial（JSON Lines）→ Python/pyserial → CSV → 数据预处理 → ModelAdapter → Streamlit

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

1. 根据实际 ESP32-DevKitC V4 pinout 确认四个 ADC GPIO，不能把示例 GPIO 当作所有开发板都通用。
2. 先使用 `firmware/esp32_soil_calibration/` 记录每支探头的干湿校准值。
3. 把校准值和实际 GPIO 写入 `firmware/esp32_irrigation_demo/`。
4. 烧录后以 115200 波特率连接，采集程序通过 `--port COMx` 指定 Windows 串口。

详细说明见：

- `docs/QUICK_CALIBRATION_CN.md`
- `docs/WIRING_TEMPLATE_CN.md`
- `docs/CSV_COMPATIBILITY_CN.md`
- `docs/DEPENDENCIES_CN.md`

## 当前边界

- 正式天气 API 尚待接口文档、鉴权方式、字段单位与更新频率确认。
- 正式模型尚需模型文件、精确特征契约、训练预处理、阈值和固定测试样例。
- 探头校准值必须通过实物测量获得，不能使用虚构默认值代替实验记录。
- 三种传感器模式会实际改变传给模型的字段；最终字段仍必须与对应模型训练契约一致。

## 验证

```powershell
.\.venv\Scripts\python.exe -m pytest
```
