# Python 包作用说明

Demo 依赖定义在 `requirements-demo.txt`，保持最小化。

| 包 | 作用 | 用在何处 |
|---|---|---|
| `pandas` | 读取回放/实时 CSV、构造模型输入表、绘制趋势所需的数据表 | Streamlit 页面、真实模型适配器 |
| `streamlit` | 提供本地 Web 演示界面、模式切换、状态提示、趋势与对比表 | `app/streamlit_app.py` |
| `pyserial` | 枚举 COM 端口并逐行读取 ESP32 的 USB 串口 JSONL | `collector/` |
| `joblib` | 加载可信来源的 `.joblib` 模型或完整 sklearn pipeline | `src/rlls_demo/model_adapter.py` |
| `pytest` | 自动检查解析、缺失值、范围、综合值、模式字段、模型接口和 CSV 往返 | `tests/` |

Python 标准库中的 `csv`、`json`、`datetime`、`logging`、`statistics`、`pathlib` 等无需额外安装。

真实模型可能额外依赖 `scikit-learn`、`numpy` 或特定版本的其他库。不要先猜版本；应按 `docs/MODEL_HANDOFF_CHECKLIST.md` 获取训练环境后再加入依赖。Arduino IDE 的 ESP32 board package 属于固件工具链，不是 Python 包。
