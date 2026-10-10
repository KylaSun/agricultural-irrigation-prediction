# CSV 格式兼容性说明

## 核对结论

2026-10-10 已对照 GitHub `origin/main`（当时提交 `ef26b8b`）中的：

- `data/merged/dataset_zone_1.csv`
- `outputs/research_core_v1/master_dataset.csv`
- `outputs/research_core_v1/sensor_configuration.csv`
- `DATA_DICTIONARY.md`

Demo 采集 CSV 包含 C1、C2、C3 所需的全部**特征列名**，因此可供当前预处理模块、`ModelAdapter` 和 Streamlit 使用。但它不是历史训练表的直接替代品，不能未经转换就拼入研究数据。

## 三类 CSV 的区别

| 层级 | 时间字段 | 土壤湿度 | 其他内容 | 是否可直接互换 |
|---|---|---|---|---|
| ESP32 采集/Demo CSV | `timestamp_utc`，带时区 | 四支原始值、校准值、综合值及最终 `soil_moisture` | 设备时间、状态、质量标记 | 供 Demo 使用 |
| GitHub merged CSV | `ts`，Europe/Rome 本地 10 分钟时间 | 单个分区的 `soil_moisture` | 历史天气、EC、pH、灌溉量 | 不可直接替代采集 CSV |
| GitHub research master | `decision_ts`/`target_ts`，UTC | 清洗后的单分区 `soil_moisture` | zone、threshold、target、`future_dry` | 是研究评估表，不是实时输入表 |

## 字段兼容情况

- C1 的 `soil_moisture`：名称兼容。单探头来源最接近历史单分区字段。
- C2 的六个 `weather_*`：名称和单位口径兼容，但实时 API 与历史 ERA5/再分析数据不是同一数据分布，必须验证来源和时间对齐。
- C3 的土温、EC、pH、过去 4 小时水量：列已预留，但当前硬件与在线数据源尚未全部提供。
- `soil_composite_pct`：Demo 新增派生字段，为至少两支有效探头的中位数。选择综合模式后会映射到模型字段 `soil_moisture`，但它不等同于历史数据中的单测点读数。

## 四探头综合规则

1. 先完成数值转换、范围检查、传感器状态处理和页面开关处理。
2. 只使用剩余的有效 `soil_*_moisture_pct`。
3. 至少需要 2 支有效探头；否则综合值为 missing。
4. 使用中位数作为 `soil_composite_pct`，降低单个异常测点的影响。
5. 同时输出 `soil_composite_count` 和 `soil_composite_spread_pct`，便于审计参与数量与测点差异。
6. 不会把 missing 当成 0，也不会对各探头的原始 ADC 值求平均。

综合值只是一种待验证的实验输入。正式模型若使用该值，需要重新验证分布、阈值和性能，必要时重新训练。

## 本地校验

```powershell
python scripts\validate_csv_contract.py data\replay\simulated_normal.csv
```

校验器检查采集层表头、C1/C2/C3 特征是否齐全，以及 `timestamp_utc` 是否带时区。它不会宣称现场数据与训练分布相同。
