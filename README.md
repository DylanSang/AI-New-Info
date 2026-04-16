# Global Intel MVP

按 `prompt.md` 需求实现的最小可用版（MVP）：
- 多源新闻采集（论坛/高校/政府/媒体可扩展）
- 去重与事件聚合
- 时间轴生成
- 可信度与影响评分
- SQLite 存储

## 目录

- `sources.yaml`：数据源与系统参数
- `collector.py`：采集层（RSS）
- `processor.py`：清洗、去重、聚类、可信度
- `timeline.py`：时间轴构建
- `impact.py`：影响评估
- `main.py`：主流程入口
- `export.py`：导出 JSON/CSV
- `web_api.py`：FastAPI 接口
- `web_app.py`：Streamlit 可视化（含 3D 地图）
- `intel.db`：运行后生成

## 运行

1. 安装依赖

```bash
pip install -r requirements.txt
```

2. 执行主流程

```bash
python main.py --config sources.yaml --db intel.db --top 5
```

3. 导出结果

```bash
python export.py --db intel.db --format json --out output/events.json
python export.py --db intel.db --format csv --out output/events.csv
```

## 网站版（可选）

1. 启动 API

```bash
uvicorn web_api:app --reload --host 0.0.0.0 --port 8000
```

2. 启动可视化面板

```bash
streamlit run web_app.py
```

支持能力：
- 事件列表筛选（类别/国家/影响分）
- 事件详情（来源与时间轴）
- 3D 世界地图事件柱状分布（按影响分抬升）
- **实时新闻标题翻译**（支持中英文互译）
- **关键词和日期搜索**（精准定位事件）
- **增强时间轴**（相关事件信息整合）

### 新功能详解

#### 1. 实时新闻标题翻译
- 支持中英文双向翻译
- 智能检测原文语言，避免重复翻译
- 可在界面中开启/关闭翻译功能
- 翻译结果与原文对照显示

#### 2. 关键词和日期搜索
- **关键词搜索**：在新闻标题中搜索特定关键词
- **日期范围搜索**：按发布日期筛选事件
- 组合搜索：支持关键词、日期、类别、国家等多维度筛选
- 实时搜索结果更新

#### 3. 增强时间轴
- 自动识别相关事件（基于类别、国家、关键词相似度）
- 将相关事件信息整合到同一时间轴
- 按时间顺序排列，便于全面了解事件发展
- 可展开查看相关事件详情

## 定时执行（Windows 任务计划程序）

可将命令 `python main.py --config sources.yaml --db intel.db` 加入任务计划程序按小时/天触发。

## 人工交互原则

若环境缺少依赖/软件，本项目遵循 `prompt.md` 约束：先人工确认，再执行自动安装。

## 后续可扩展

- 增加军事、人文来源配置
- 增加网页抓取/API 采集插件
- 替换规则聚类为向量召回 + LLM 事件融合
- 为地图增加真实地理编码与时间滑块动画
# AI-New-Info
