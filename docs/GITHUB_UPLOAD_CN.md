# GitHub 上传检查表

## 上传前验证

```powershell
python -m pytest -q
python scripts\self_check.py
python scripts\validate_csv_contract.py data\replay\simulated_normal.csv
```

然后检查：

```powershell
git status --short
git diff --check
```

## 建议纳入本次提交

- `app/`：Streamlit 页面
- `collector/`：串口采集与端口枚举
- `config/`：数据、模式、模型和成本契约
- `data/replay/`：明确标注的模拟测试数据
- `docs/`：接线、校准、CSV 兼容性、依赖和演示文档
- `firmware/`：ESP32 示例固件
- `models/README.md`：模型目录说明，不包含未经确认的真实模型
- `scripts/`：启动、模拟数据、回放生成和检查脚本
- `src/rlls_demo/`：解析、预处理、CSV 与模型适配器
- `tests/`、`pytest.ini`、`conftest.py`：自动测试
- `requirements-demo.txt`、`README_DEMO_CN.md`、`.gitignore`

## 不应上传

- `.venv/`、`.venv-codex-backup/`
- `.pytest-*`、`__pycache__/`、`*.pyc`
- `data/live/*.csv` 中的现场/实时数据
- `.env`、`.streamlit/secrets.toml`、API Key、串口设备私密信息
- 来源不明或版本不匹配的 `.pkl`/`.joblib`

这些项目已尽量加入 `.gitignore`。天气 API 接入后，只提交环境变量名称和示例配置，不提交真实密钥。

## 建议提交命令

先查看即将加入的内容，不要直接盲目提交全部文件：

```powershell
git add .gitignore README.md README_DEMO_CN.md requirements-demo.txt pytest.ini conftest.py
git add app collector config data/replay docs firmware models scripts src/rlls_demo tests
git status --short
git diff --cached --stat
```

确认列表正确后再执行：

```powershell
git commit -m "Add ESP32 irrigation demo scaffold and four-probe composite"
git push origin main
```

`git push` 会修改远端仓库，执行前应再次确认暂存区内容。本项目不会自动 push。
