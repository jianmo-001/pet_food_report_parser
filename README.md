# 自动 PDF 检测报告入库

这个项目用于把检测报告 PDF 自动解析并写入飞书多维表格。生产识别链路不依赖大模型：优先解析 PDF 文本，失败或扫描件再走本地 OCR，最后用模板规则提取字段。

## 功能

- 从飞书多维表格读取 `待解析` 的检测报告记录。
- 下载管理员上传的 PDF 附件。
- 提取报告基础信息和检测项目明细。
- 回填“检测报告主表”，批量新增“检测项目明细表”。
- 解析失败时写入错误原因，并通过飞书机器人通知管理员。
- 支持 dry-run，本地调试不会写入飞书。

## 快速开始

```bash
cd /Users/yangrunxin/Desktop/自动pdf检测
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev,ocr]"
cp .env.example .env
```

先本地解析一个 PDF：

```bash
python -m pdf_report_ingestor.cli parse-local data/samples/example.pdf
```

轮询飞书待解析记录：

```bash
python -m pdf_report_ingestor.cli poll --once
```

默认 `DRY_RUN=true`，不会真实写飞书。确认配置无误后再改成 `DRY_RUN=false`。

## 飞书多维表格建议字段

### 检测报告主表

- PDF附件
- 报告编号
- 样品名称
- 检测机构
- 委托单位
- 报告日期
- 报告结论
- 产品分类
- 解析状态
- 错误原因
- 解析模板
- 其他信息JSON
- 原文文本
- 关联明细

### 检测项目明细表

- 关联报告
- 检测项目
- 检测值
- 单位
- 标准要求
- 检测方法
- 单项结论
- 来源页码
- 来源文本片段
- 明细额外信息JSON

## 配置

所有配置通过 `.env` 读取。字段名可以在 `.env` 中按你的多维表格实际字段调整。

关键配置：

- `FEISHU_APP_ID`
- `FEISHU_APP_SECRET`
- `FEISHU_BITABLE_APP_TOKEN`
- `FEISHU_REPORT_TABLE_ID`
- `FEISHU_ITEM_TABLE_ID`
- `FEISHU_BOT_WEBHOOK`
- `DRY_RUN`

## 模板规则

模板规则在 `config/templates.yaml`。新增检测机构或新版式时，增加一条模板配置即可。规则主要分三类：

- `keywords`：用于判断 PDF 属于哪个模板。
- `fields`：报告主表字段的正则提取规则。
- `items`：检测项目明细的正则提取规则。

## 备注

- OCR 默认优先尝试 PaddleOCR；如果未安装 OCR 依赖，扫描件会解析失败并通知管理员。
- 飞书权限需要在多维表格里配置管理员、客服、研发三类角色的视图和字段权限。
