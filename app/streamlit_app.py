from __future__ import annotations

import html
import json
import math
import statistics
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import pandas as pd
import streamlit as st

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from rlls_demo.model_adapter import ModelContractError, load_adapter
from rlls_demo.paths import CONFIG_DIR
from rlls_demo.preprocessing import process_record
from rlls_demo.schema import feature_order, load_modes


st.set_page_config(page_title="RLLS Irrigation Lab", page_icon="💧", layout="wide")
st.markdown(
    """
    <style>
    :root { --ink:#17352c; --muted:#60736c; --accent:#147a62; --line:#d7e2dc; --wash:#f3f7f4; }
    .stApp { background: #fbfcfa; color: var(--ink); }
    /* Streamlit scrolls the page inside stMain rather than on the browser body.
       Keep that internal scrollbar visible so mouse dragging and touch panning
       remain discoverable in narrow demo windows. */
    [data-testid="stMain"] {
        overflow-y: scroll !important;
        overscroll-behavior-y: contain;
        touch-action: pan-y;
        scrollbar-gutter: stable;
        scrollbar-width: auto;
        scrollbar-color: #7da394 #e5eee9;
    }
    [data-testid="stMain"]::-webkit-scrollbar { width: 12px; }
    [data-testid="stMain"]::-webkit-scrollbar-track { background: #e5eee9; }
    [data-testid="stMain"]::-webkit-scrollbar-thumb {
        background: #7da394;
        border: 3px solid #e5eee9;
        border-radius: 999px;
    }
    [data-testid="stMain"]::-webkit-scrollbar-thumb:hover { background: var(--accent); }
    h1, h2, h3 { color: var(--ink); letter-spacing: -0.02em; }
    [data-testid="stMetric"] { background: var(--wash); border-radius: 14px; padding: 14px; }
    [data-testid="stMetricLabel"] { color: var(--muted); }
    [data-testid="stMetricValue"] { font-size:1.55rem; line-height:1.15; font-variant-numeric:tabular-nums; }
    .mock-banner { background:#fff4cc; color:#5e4600; padding:12px 16px; border-radius:12px; margin:8px 0 18px; }
    .status-line { display:flex; gap:12px; flex-wrap:wrap; margin:4px 0 18px; }
    .status-chip { background:#e9f4ef; color:#205c4c; border-radius:999px; padding:5px 10px; font-size:0.88rem; }
    .status-chip.warn { background:#fff0d6; color:#764900; }
    .status-chip.bad { background:#fde7e4; color:#8a2920; }
    .prediction-panel {
        background:#fff8df;
        border:1px solid #ead58c;
        border-radius:14px;
        padding:18px 20px;
        margin:8px 0 14px;
    }
    .prediction-panel.real { background:#eaf5ef; border-color:#a8cdbd; }
    .prediction-head { display:flex; justify-content:space-between; align-items:center; gap:12px; }
    .prediction-state { color:#705200; font-size:0.82rem; font-weight:750; letter-spacing:0.02em; }
    .prediction-panel.real .prediction-state { color:#205c4c; }
    .prediction-badge {
        background:#5e4600; color:#fff8df; border-radius:999px;
        padding:4px 9px; font-size:0.72rem; font-weight:750;
    }
    .prediction-panel.real .prediction-badge { background:#205c4c; color:#f5fffa; }
    .prediction-value { color:var(--ink); font-size:2rem; line-height:1.15; font-weight:780; margin:10px 0 6px; }
    .prediction-meaning { color:#5f542e; line-height:1.5; margin:0; max-width:62ch; }
    .prediction-panel.real .prediction-meaning { color:#405d53; }
    .prediction-facts {
        display:grid; grid-template-columns:repeat(3,minmax(0,1fr));
        gap:10px; margin-top:16px; padding-top:14px; border-top:1px solid #e8dba9;
    }
    .prediction-panel.real .prediction-facts { border-top-color:#bdd8cc; }
    .prediction-fact span { display:block; color:#766b45; font-size:0.76rem; margin-bottom:3px; }
    .prediction-panel.real .prediction-fact span { color:#60736c; }
    .prediction-fact strong { color:var(--ink); font-size:0.98rem; font-variant-numeric:tabular-nums; }
    @media (max-width:760px) {
        .prediction-head { align-items:flex-start; flex-direction:column-reverse; }
        .prediction-facts { grid-template-columns:1fr; }
    }
    code { color:#165d4d !important; }
    </style>
    """,
    unsafe_allow_html=True,
)


@st.cache_data(ttl=1, show_spinner=False)
def read_csv_cached(path: str) -> pd.DataFrame:
    return pd.read_csv(path)


@st.cache_data(show_spinner=False)
def load_configs() -> tuple[dict[str, Any], dict[str, Any]]:
    modes = load_modes()
    with (CONFIG_DIR / "hardware_costs.json").open(encoding="utf-8") as handle:
        costs = json.load(handle)
    return modes, costs


@st.cache_resource(show_spinner=False)
def adapter_for(mode: str, order: tuple[str, ...]):
    return load_adapter(CONFIG_DIR / "models.json", mode, order)


def synthetic_frame(rows: int = 60) -> pd.DataFrame:
    now = datetime.now(timezone.utc).replace(microsecond=0)
    data = []
    for i in range(rows):
        ts = now - timedelta(seconds=rows - i - 1)
        phase = i / 8
        record = {
            "timestamp_utc": ts.isoformat().replace("+00:00", "Z"), "device_ms": i * 1000,
            "weather_temp": 23.5, "weather_humidity": 64, "weather_rain": 0,
            "weather_pressure": 1012, "weather_wind_speed": 9.2, "weather_radiation": 410,
            "simulated": True, "mode": "c2_low_cost_hybrid", "quality_flag": "simulated", "quality_detail": "SIMULATED_DATA",
        }
        for index, offset in enumerate((-3.0, -1.0, 1.5, 3.5), start=1):
            pct = 49 + offset + 3 * math.sin(phase + index * 0.15)
            record[f"soil_{index}_raw"] = 3200 - int(pct * 18)
            record[f"soil_{index}_moisture_pct"] = pct
            record[f"soil_{index}_status"] = "simulated"
        probe_values = [record[f"soil_{index}_moisture_pct"] for index in range(1, 5)]
        record["soil_composite_pct"] = round(float(statistics.median(probe_values)), 2)
        record["soil_composite_count"] = len(probe_values)
        record["soil_composite_spread_pct"] = round(max(probe_values) - min(probe_values), 2)
        data.append(record)
    return pd.DataFrame(data)


def clean_value(value: Any) -> Any:
    if pd.isna(value):
        return None
    if isinstance(value, str) and value.lower() in {"true", "false"}:
        return value.lower() == "true"
    return value


def latest_record(frame: pd.DataFrame) -> dict[str, Any]:
    if frame.empty:
        raise ValueError("CSV contains no records")
    return {key: clean_value(value) for key, value in frame.iloc[-1].to_dict().items()}


def sensor_disabled_fields(enabled: dict[str, bool]) -> set[str]:
    mapping = {
        f"soil_{index}": {f"soil_{index}_raw", f"soil_{index}_moisture_pct"}
        for index in range(1, 5)
    }
    disabled: set[str] = set()
    for sensor, fields in mapping.items():
        if not enabled.get(sensor, False):
            disabled.update(fields)
    return disabled


def fmt(value: Any, suffix: str = "") -> str:
    if value is None or pd.isna(value):
        return "missing"
    if isinstance(value, bool):
        return ("yes" if value else "no") + suffix
    if isinstance(value, (int, float)):
        return f"{value:.1f}{suffix}"
    return f"{value}{suffix}"


MODES, COSTS = load_configs()
labels = {key: value["label"] for key, value in MODES["modes"].items()}

st.title("RLLS · Low-cost Irrigation Lab")
st.caption("硬件数据链路与 Sensor Ablation 演示台｜研究用途，不控制灌溉设备")
st.markdown('<div class="mock-banner"><strong>当前模型：MockModel</strong> — 仅验证数据链路与界面，不代表真实模型、准确率或农业建议。</div>', unsafe_allow_html=True)

with st.sidebar:
    st.header("实验设置")
    source = st.radio("数据来源", ["模拟数据", "CSV 回放", "实时串口 CSV"], help="串口由独立 collector 进程读取；本页面不会打开 COM 端口。")
    mode = st.selectbox("模型配置 / 基线", list(labels), format_func=lambda item: labels[item])
    st.caption("C1/C2/C3 字段与研究代码一致；在线模型文件和天气 API 契约仍待交接。")
    replay_file = None
    if source == "CSV 回放":
        uploaded = st.file_uploader("上传 CSV（可选）", type=["csv"])
        choices = sorted((PROJECT_ROOT / "data/replay").glob("*.csv"))
        if uploaded is None:
            replay_file = st.selectbox("内置回放数据", choices, format_func=lambda item: item.name) if choices else None
    live_path = st.text_input("实时 CSV 路径", str(PROJECT_ROOT / "data/live/sensor_readings.csv")) if source == "实时串口 CSV" else None
    st.divider()
    st.subheader("SEN0308 探头开关")
    source_options = [f"soil_{index}" for index in range(1, 5)] + ["soil_composite"]
    active_probe = st.selectbox(
        "模型土壤湿度来源",
        source_options,
        format_func=lambda value: "四探头综合值（有效值中位数）" if value == "soil_composite" else value.replace("soil_", "soil_0"),
    )
    enabled = {}
    for key, label in [(f"soil_{index}", f"soil_0{index}") for index in range(1, 5)]:
        enabled[key] = st.toggle(label, value=mode != "weather_only", disabled=mode == "weather_only")
    st.caption("可选单测点或综合值。综合值至少需要 2 支有效探头，使用中位数；关闭开关会真实影响输入。")
    st.button("刷新数据", width="stretch")

try:
    if source == "模拟数据":
        frame = synthetic_frame()
        connection = "SIMULATED — no ESP32"
    elif source == "CSV 回放":
        if uploaded is not None:
            frame = pd.read_csv(uploaded)
        elif replay_file is not None:
            frame = read_csv_cached(str(replay_file))
        else:
            frame = pd.DataFrame()
        connection = "REPLAY — no live serial"
    else:
        if not live_path or not Path(live_path).exists():
            frame = pd.DataFrame()
            connection = "DISCONNECTED — collector CSV not found"
        else:
            frame = read_csv_cached(live_path)
            connection = "CSV ACTIVE — collector managed separately"

    raw_latest = latest_record(frame)
    disabled = sensor_disabled_fields(enabled)
    replay_now = None
    if source == "CSV 回放" and str(raw_latest.get("quality_flag", "")).lower() != "stale":
        replay_time = pd.to_datetime(raw_latest.get("timestamp_utc"), errors="coerce", utc=True)
        if not pd.isna(replay_time):
            replay_now = replay_time.to_pydatetime() + timedelta(seconds=1)
    processed = process_record(raw_latest, mode, active_probe=active_probe, now=replay_now, stale_after_seconds=10, disabled_fields=disabled)
    order = feature_order(mode, MODES)
    adapter = adapter_for(mode, tuple(order))
    prediction = adapter.predict(processed.features)
    last_update = raw_latest.get("timestamp_utc", "unknown")

    status_class = "bad" if processed.quality_flag in {"invalid", "out_of_range"} else "warn" if processed.quality_flag in {"missing", "stale", "simulated"} else ""
    st.markdown(
        f'<div class="status-line"><span class="status-chip">Source · {source}</span><span class="status-chip">ESP32 · {connection}</span><span class="status-chip {status_class}">Quality · {processed.quality_flag}</span><span class="status-chip">Updated · {last_update}</span></div>',
        unsafe_allow_html=True,
    )

    left, right = st.columns([1.45, 1])
    with left:
        st.subheader("最新现场读数")
        probe_columns = st.columns(4)
        for index, column in enumerate(probe_columns, start=1):
            column.metric(f"soil_0{index} · %", fmt(processed.record.get(f"soil_{index}_moisture_pct")))
        composite_value, composite_detail = st.columns([1, 3])
        composite_value.metric(
            "综合值 · %",
            fmt(processed.record.get("soil_composite_pct")),
        )
        composite_detail.markdown(
            f"**综合值依据**  有效探头 {processed.record.get('soil_composite_count', 0)} 支  ·  "
            f"测点极差 {fmt(processed.record.get('soil_composite_spread_pct'), ' pp')}"
        )
        composite_detail.caption("只使用通过范围和状态检查的探头；少于 2 支时综合值为 missing。")
        e, f, g, h = st.columns(4)
        e.metric("气温 · °C", fmt(processed.record.get("weather_temp")))
        f.metric("降雨 · mm", fmt(processed.record.get("weather_rain")))
        g.metric("风速 · km/h", fmt(processed.record.get("weather_wind_speed")))
        h.metric("辐射 · W/m²", fmt(processed.record.get("weather_radiation")))

        st.subheader("最近趋势")
        trend_fields = [f"soil_{index}_moisture_pct" for index in range(1, 5) if f"soil_{index}_moisture_pct" in frame.columns]
        if "soil_composite_pct" in frame.columns:
            trend_fields.append("soil_composite_pct")
        if trend_fields:
            chart = frame.tail(60).copy()
            if "timestamp_utc" in chart:
                chart["timestamp_utc"] = pd.to_datetime(chart["timestamp_utc"], errors="coerce", utc=True)
                chart = chart.set_index("timestamp_utc")
            st.line_chart(chart[trend_fields], height=260)
        else:
            st.info("当前数据没有可绘制的趋势字段。")

    with right:
        st.subheader("模型预测结果")
        available_inputs = sum(value is not None for value in processed.features.values())
        completeness = available_inputs / len(order) if order else 0.0
        result_value = f"类别 {prediction.prediction}"
        probability_text = f"{prediction.probability:.1%}" if prediction.probability is not None else "N/A"
        soil_source = "不使用土壤探头" if "soil_moisture" not in order else (
            "四探头综合中位数" if active_probe == "soil_composite" else active_probe.replace("soil_", "soil_0")
        )
        if prediction.is_mock:
            panel_class = "prediction-panel"
            state_text = "模拟链路输出"
            badge_text = "MOCK · 非真实预测"
            meaning_text = "目标定义和正式模型尚未交付。这个类别只能证明数据已经进入预测接口，不能解读为“应该灌溉”或“不需要灌溉”。"
            score_label = "接口测试分数"
        else:
            panel_class = "prediction-panel real"
            state_text = "已加载模型输出"
            badge_text = "REAL MODEL"
            meaning_text = "请结合已确认的正类含义、决策阈值和模型适用边界解释该结果。"
            score_label = "模型概率输出"
        st.markdown(
            f"""
            <section class="{panel_class}" aria-label="模型预测结果">
              <div class="prediction-head">
                <span class="prediction-state">{html.escape(state_text)}</span>
                <span class="prediction-badge">{html.escape(badge_text)}</span>
              </div>
              <div class="prediction-value">{html.escape(result_value)}</div>
              <p class="prediction-meaning">{html.escape(meaning_text)}</p>
              <div class="prediction-facts">
                <div class="prediction-fact"><span>{html.escape(score_label)}</span><strong>{html.escape(probability_text)}</strong></div>
                <div class="prediction-fact"><span>有效模型输入</span><strong>{available_inputs}/{len(order)} · {completeness:.0%}</strong></div>
                <div class="prediction-fact"><span>土壤湿度来源</span><strong>{html.escape(soil_source)}</strong></div>
              </div>
            </section>
            """,
            unsafe_allow_html=True,
        )
        if available_inputs < len(order):
            st.warning(f"当前缺少 {len(order) - available_inputs} 个模型输入字段；正式模型能否处理缺失值必须以训练 pipeline 为准。")
        st.caption(f"当前配置：{labels[mode]} · 数据质量：{processed.quality_flag}")

        input_table = pd.DataFrame({
            "feature": order,
            "value": [processed.features.get(name) for name in order],
            "state": ["missing" if processed.features.get(name) is None else "available" for name in order],
        })
        with st.expander(f"查看本次模型输入（{available_inputs}/{len(order)} 个可用）", expanded=False):
            st.dataframe(input_table, hide_index=True, width="stretch", height=260)
        if processed.issues:
            with st.expander(f"数据质量提示（{len(processed.issues)}）", expanded=True):
                for issue in processed.issues:
                    st.write(f"- {issue}")

    st.subheader("C1 / C2 / C3 与额外基线对比")
    comparison = []
    cost_items = COSTS["items"]
    for mode_key, definition in MODES["modes"].items():
        fields = feature_order(mode_key, MODES)
        candidate = process_record(raw_latest, mode_key, active_probe=active_probe, now=replay_now, stale_after_seconds=10, disabled_fields=disabled)
        result = adapter_for(mode_key, tuple(fields)).predict(candidate.features)
        components = COSTS["mode_components"][mode_key]
        quoted = [cost_items[name]["unit_cost"] for name in components]
        cost = sum(cost_items[name]["unit_cost"] * quantity for name, quantity in components.items())
        cost_label = f"¥{cost:.2f}" if components and all(value > 0 for value in quoted) else "无现场硬件" if not components else "待录入报价"
        unavailable = COSTS.get("unavailable_for_current_purchase", {}).get(mode_key, [])
        comparison.append({
            "mode": definition["label"], "field_count": len(fields), "selected_probe": active_probe if "soil_moisture" in fields else "not used",
            "available_inputs": sum(value is not None for value in candidate.features.values()),
            "current_purchase_gap": ", ".join(unavailable) if unavailable else "none",
            "quality": candidate.quality_flag, "prediction": f"MOCK {result.prediction}", "probability": f"{result.probability:.1%}", "hardware_cost": cost_label,
        })
    st.dataframe(pd.DataFrame(comparison), hide_index=True, width="stretch")
    st.caption("四支 SEN0308 是四个位置，不是四个模型特征。综合值是 Demo 新增的派生输入，不等同于历史训练数据中的单测点 soil_moisture。C3 当前缺少 EC、pH 和过去4小时用水量；两个土温字段的在线天气服务契约也尚未确认。成本 0 表示待录入报价。")

except (ValueError, ModelContractError, pd.errors.ParserError) as exc:
    st.error(f"无法处理当前数据：{exc}")
    st.info("可切换到“模拟数据”，或检查 CSV 表头、时间戳与字段类型。")
