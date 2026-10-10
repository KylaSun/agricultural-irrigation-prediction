# 演示前检查表

## 软件

- [ ] `python -m pytest -q` 通过
- [ ] `python -m streamlit run app/streamlit_app.py --server.headless true` 能启动
- [ ] 回放 CSV 五类样例均可读取
- [ ] MockModel 警告清晰可见
- [ ] 成本未填时显示“待录入报价”，不是 ¥0 免费
- [ ] 关闭传感器后模型输入字段真的变为 missing

## 硬件（有实物时）

- [ ] 精确板型和 GPIO 记录完成
- [ ] USB 线支持数据；COM 端口已确认
- [ ] `USE_SIMULATED_VALUES=false`
- [ ] 四支 SEN0308 逐个验证；`soil_1_status` 至 `soil_4_status` 均为 `ok`
- [ ] ADC 电压、供电、共地与防水检查完成
- [ ] Arduino Serial Monitor 已关闭，端口未被占用

## 数据与叙事

- [ ] 电脑时间与时区正确；CSV 时间为 UTC
- [ ] 明确当前使用实时、模拟或回放数据
- [ ] 不宣称未经验证的精度、节水、产量或传感器性能
- [ ] 能说明 target 定义、模型版本和阈值；不能说明时继续标注 Mock
- [ ] 准备离线回放作为串口故障降级方案
