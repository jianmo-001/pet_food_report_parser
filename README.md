# 自动 PDF 检测报告入库

这个项目用于把检测报告 PDF 自动解析并写入飞书多维表格。生产识别链路不依赖大模型：优先解析 PDF 文本，失败或扫描件再走本地 OCR，最后用模板规则提取字段。

GitHub 仓库：

```text
https://github.com/jianmo-001/pet_food_report_parser
```

## 功能

- 从飞书多维表格读取 `待解析` 的检测报告记录。
- 下载管理员上传的 PDF 附件。
- 提取报告基础信息和检测项目明细。
- 回填“检测报告主表”，批量新增“检测项目明细表”。
- 解析失败时写入错误原因，并通过飞书机器人通知管理员。
- 支持 dry-run，本地调试不会写入飞书。
- 支持本地导出 Markdown、JSON、主表 CSV、明细表 CSV，方便先人工检查解析效果。

## 已适配模板

当前已针对示例报告适配以下机构/版式：

- SGS / 通标标准技术服务
- 华测 / CTI
- 天祥 / Intertek
- 梅里埃 / Merieux NutriSciences

系统不是“任意 PDF 都自动理解”的通用 AI 识别器，而是“通用管线 + 模板规则”。遇到新机构或新版式时，需要新增模板规则或解析器。

## 快速开始

```bash
git clone https://github.com/jianmo-001/pet_food_report_parser.git
cd pet_food_report_parser
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev,ocr]"
cp .env.example .env
```

先本地解析一个 PDF：

```bash
python -m pdf_report_ingestor.cli parse-local data/samples/example.pdf
```

导出本地解析结果：

```bash
python -m pdf_report_ingestor.cli export-local data/samples/example.pdf
```

导出后会在 `output/机构名/` 下生成：

```text
报告编号.md
报告编号.json
报告编号_main.csv
报告编号_items.csv
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
- 替代报告编号
- 样品名称
- 样品编号
- 样品批号
- 样品规格
- 样品数量
- 样品状态
- 样品来源
- 客户名称
- 客户地址
- 检测机构
- 检测机构地址
- 报告日期
- 发布日期
- 签发日期
- 样品接收日期
- 检测开始日期
- 检测结束日期
- 检测周期
- 生产日期
- 生产商
- 检验类别
- 检测项目概述
- 判定标准
- 报告结论
- 备注
- 声明
- 解析状态
- 错误原因
- 解析模板
- 文本来源
- 检测项目数量
- 其他信息JSON
- 原文文本
- 关联明细

主表字段采用“同义字段合并后的规范化并集”。例如：

- `证书编号`、`CoA No.` 统一为 `报告编号`
- `委托单位`、`客户名称`、`Applicant` 统一为 `客户名称`
- `SGS样品ID`、`CTI样品编号`、`Sample Number` 统一为 `样品编号`
- `到样日期`、`Receive Date` 统一为 `样品接收日期`
- `生产单位`、`Producer` 统一为 `生产商`

### 检测项目明细表

- 关联报告
- 检测项目
- 单位
- 检测方法
- 检测结果
- 定量限/检出限
- 限值
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
- PDF 原件、`.env`、`output/` 解析结果、虚拟环境和缓存文件都已写入 `.gitignore`，不要提交到 GitHub。
