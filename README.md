# 自动 PDF 检测报告入库

这个项目用于把检测报告 PDF 自动解析并写入飞书多维表格。生产识别链路不依赖大模型：优先解析 PDF 文本，失败或扫描件再走本地 OCR，最后用模板规则提取字段。

GitHub 仓库：

```text
https://github.com/jianmo-001/pet_food_report_parser
```

## 功能

- 从飞书多维表格读取 `待解析` 的检测报告记录，默认使用“产品检测值宽表”作为上传入口。
- 下载管理员上传的 PDF 附件。
- 提取报告基础信息和检测项目明细。
- 回填“产品检测值宽表”当前行，把检测项目转成字段列，用于跨报告对比。
- 可选批量新增“检测项目明细表”，用于保留完整明细。
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

生产第一版建议使用轮询，不依赖飞书自动化插件或公网 webhook。默认流程是：管理员在 `产品检测值宽表` 的 `PDF附件` 字段上传 PDF，并把 `解析状态` 设为 `未解析` 或 `待解析`；脚本会下载附件、解析 PDF，然后回填同一行的品牌、产品、报告信息和各项检测值。

```bash
python -m pdf_report_ingestor.cli poll --once
```

持续轮询可以直接运行：

```bash
python -m pdf_report_ingestor.cli poll
```

轮询间隔由 `.env` 里的 `POLL_INTERVAL_SECONDS` 控制，默认 60 秒。当前脚本也会处理 `解析状态` 为空但已经上传了 `PDF附件` 的记录，方便测试；正式使用时建议统一填 `未解析`。

初始化本地 SQLite 数据库：

```bash
python -m pdf_report_ingestor.cli init-db
```

启动报告详情页服务：

```bash
python -m pdf_report_ingestor.cli web --host 127.0.0.1 --port 8000
```

解析成功后，脚本会把完整解析结果写入 SQLite，把 PDF 保存到 `REPORT_PDF_DIR`，并在飞书表格 `详情页链接` 字段写入报告入口。本地开发默认类似 `http://127.0.0.1:8000/report/rec_xxx`；服务器部署时设置 `PUBLIC_BASE_URL=http://公网IP` 或 `PUBLIC_BASE_URL=https://域名`，让飞书链接指向 Nginx 暴露的 80/443 入口，而不是直接暴露后端 8000 端口。

把本地 `output/` 里的 CSV 创建为新的飞书多维表格：

```bash
python -m pdf_report_ingestor.cli import-output-to-feishu --output output
```

把本地 `output/` 里的 CSV 写入已有多维表格：

```bash
python -m pdf_report_ingestor.cli append-output-to-feishu --output output
```

`append-output-to-feishu` 需要你先在飞书里手动建好多维表格和两张表。`poll` 默认需要一张 `产品检测值宽表`，并在 `.env` 里填写：

```text
FEISHU_BITABLE_APP_TOKEN=多维表格 app_token
FEISHU_WIDE_TABLE_ID=产品检测值宽表 table_id
FEISHU_UPLOAD_TABLE_MODE=wide
FEISHU_ITEM_TABLE_ID=检测项目明细表 table_id，可选
```

如果要切回旧版“检测报告主表上传 PDF”的流程，把 `FEISHU_UPLOAD_TABLE_MODE` 改成 `report`，并填写 `FEISHU_REPORT_TABLE_ID`。

批量处理一个文件夹里的 PDF，并直接创建新的飞书多维表格：

```bash
python -m pdf_report_ingestor.cli process-folder "/path/to/pdf-folder" \
  --output output/batch \
  --import-to-feishu
```

如果部分 PDF 解析失败，默认不会导入飞书，避免漏数据。确认可以接受只导入成功文件时，增加：

```bash
python -m pdf_report_ingestor.cli process-folder "/path/to/pdf-folder" \
  --output output/batch \
  --import-to-feishu \
  --allow-partial
```

默认 `DRY_RUN=true`，不会真实写飞书。确认配置无误后再改成 `DRY_RUN=false`。

## 第一版生产流程

1. 飞书 `产品检测值宽表` 第一列设置为 `产品名称`，另建附件字段 `PDF附件`。
2. 管理员新增一行，上传 PDF 到 `PDF附件`。
3. 管理员把 `解析状态` 填成 `未解析`，也可以先留空用于测试。
4. 本地或服务器运行 `python -m pdf_report_ingestor.cli poll`。
5. 脚本发现待解析记录后，将状态改为 `解析中`。
6. 脚本通过飞书 Drive API 下载附件，调用本项目的 PDF 解析规则。
7. 解析成功后，脚本回填当前宽表行，把 `解析状态` 改为 `解析成功`，并可选向明细表批量新增检测项目。
8. 脚本同时把完整结构化数据写入 SQLite，把 PDF 保存到本地，并回填 `详情页链接`。
9. 解析失败时，脚本把 `解析状态` 改为 `解析失败`，并写入 `错误原因`。

这个方案不需要先生成 `output/`。`output/` 主要用于本地查看四份示例报告的解析结果，或者把历史解析结果一次性导入已有表格。

## 飞书多维表格建议字段

### 检测报告主表

- PDF文件名
- PDF附件
- 报告编号
- 替代报告编号
- 品牌名称
- 产品名称
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
- 报告日期
- 样品接收日期
- 检测开始日期
- 检测结束日期
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
- 详情页链接
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

飞书多维表格第一列是主字段/索引列，不能作为普通附件字段移动使用。建议第一列保留 `PDF文件名`，第二列设置为 `PDF附件`，留给管理员上传原始 PDF。脚本写入解析结果时默认不填 `PDF附件`，不会覆盖附件列。

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

### 产品检测值宽表

宽表现在是默认上传入口。管理员直接在这张表上传 PDF，脚本解析后回填同一行。建议第一列设置为 `产品名称`，其余字段包括：

- PDF文件名
- PDF附件
- 解析状态
- 错误原因
- 品牌名称
- 报告编号
- 样品名称
- 检测机构
- 报告日期
- 样品接收日期
- 检测开始日期
- 检测结束日期
- 详情页链接
- 粗蛋白
- 粗脂肪
- 水分
- 粗灰分
- 粗纤维
- 钙
- 总磷
- 钙磷比
- 钠
- 钾
- 镁
- 锌
- 铁
- 铜
- 锰
- 碘
- 硒
- 牛磺酸
- 淀粉
- 黄曲霉毒素B1
- 沙门氏菌
- 氯化物
- 维生素A
- 维生素D
- 维生素E
- 维生素B1
- 维生素B6
- 维生素B12
- 叶酸
- 胆碱
- 烟酸
- 泛酸
- 核黄素
- 净含量
- 未映射检测项目JSON

宽表里单位稳定的检测项会把单位写进字段名，例如 `粗蛋白（%）`、`维生素A（IU/kg）`，单元格只写检测值，便于筛选和比较。单位不稳定或没有稳定单位的字段仍保留原字段名，并在值里保留单位信息，避免误合并。

如果已经手动建好了 `产品检测值宽表`，可以用脚本自动补齐缺失字段：

```bash
python -m pdf_report_ingestor.cli ensure-wide-fields
```

脚本会跳过已有字段，只新增缺失字段。`PDF附件` 会创建为附件字段；宽表里的报告日期、样品接收日期、检测开始日期、检测结束日期会创建为飞书日期字段；其他字段创建为文本字段。

### 云空间归档

解析成功后，脚本会根据 PDF 文件名（其次样品名）自动判断它属于哪个产品，把 PDF 归档到共享文件夹里对应的子目录，并在宽表回写归档位置。整条识别链路是纯规则、不依赖大模型。

1. 归档路由规则在 `config/archive_rules.yaml`，按文件夹维护两类匹配：

```yaml
folders:
  - name: "P40Plus"            # 必须与共享文件夹里的子目录名完全一致
    codes: ["P40PLUS"]          # 产品代号：整词、忽略大小写、去空格
  - name: "零食"
    keywords: ["宠物零食"]       # 类目关键词：中文子串
    subfolders:                  # 可选二级子目录
      - name: "补水汤包"
        keywords: ["补水汤包"]
```

匹配优先级：产品代号优先于类目关键词；同层内命中字符串最长者优先；并列冲突判为“未匹配”。代号型的新文件夹（如 `P50`）无需配置即可从文件夹名自动派生代号；中文类目型新品匹配不到时会进未匹配清单，提示补一条规则。

2. 在 `.env` 里启用归档，并填入共享文件夹（归档根目录）的 token：

```text
FEISHU_ARCHIVE_ENABLED=true
FEISHU_ARCHIVE_RULES=config/archive_rules.yaml
FEISHU_ARCHIVE_ROOT_TOKEN=共享文件夹 token，取自 /drive/folder/<token>
FEISHU_ARCHIVE_DOMAIN=https://你的企业域名.feishu.cn
FIELD_ARCHIVE_URL=归档文件链接
FIELD_ARCHIVE_PATH=归档路径
FIELD_ARCHIVE_ERROR=归档错误
```

归档只在解析成功后执行；原 `PDF附件` 不会被移动或删除，目标文件夹同名同大小的文件不会重复上传。成功时回写 `归档路径`（如 `诚实一口大货报告/零食/补水汤包`）和 `归档文件链接`；二级子目录在云端不存在时回落到顶层根目录。匹配不到或上传失败时，解析状态仍保持成功，只写入 `归档错误`，并把该文件追加到 `output/archive_unmatched.csv` 供人工复核。

上线前可先用与共享文件夹结构一致的本地镜像，全量验证路由准确率（不联网、不写任何东西）：

```bash
python scripts/validate_archive_router.py "/path/to/本地镜像文件夹"
```

## 配置

所有配置通过 `.env` 读取。字段名可以在 `.env` 中按你的多维表格实际字段调整。

关键配置：

- `FEISHU_APP_ID`
- `FEISHU_APP_SECRET`
- `FEISHU_BITABLE_APP_TOKEN`
- `FEISHU_REPORT_TABLE_ID`
- `FEISHU_ITEM_TABLE_ID`
- `FEISHU_WIDE_TABLE_ID`
- `FEISHU_UPLOAD_TABLE_MODE`
- `FEISHU_BOT_WEBHOOK`
- `FEISHU_FOLDER_TOKEN`
- `FEISHU_OUTPUT_BITABLE_NAME`
- `DATABASE_URL`
- `REPORT_PDF_DIR`
- `DETAIL_BASE_URL`
- `DRY_RUN`

如果只是把本地 `output/` 导入成一个新的多维表格，至少需要：

```text
DRY_RUN=false
FEISHU_APP_ID=你的企业自建应用 App ID
FEISHU_APP_SECRET=你的企业自建应用 App Secret
FEISHU_FOLDER_TOKEN=可选，目标飞书文件夹 token
FEISHU_OUTPUT_BITABLE_NAME=宠物食品检测报告解析结果
FEISHU_LINK_SHARE_ENTITY=tenant_editable
```

`FEISHU_FOLDER_TOKEN` 不填时，多维表格会创建在应用默认可访问位置；填入某个云空间文件夹 token 后，会创建到该文件夹。导入命令执行成功后会输出：

```json
{
  "app_token": "...",
  "url": "https://feishu.cn/base/...",
  "permission": {...},
  "tables": {
    "检测报告主表": {"table_id": "...", "records": 4},
    "检测项目明细表": {"table_id": "...", "records": 60}
  }
}
```

其中 `url` 就是可以打开的多维表格链接。

`FEISHU_LINK_SHARE_ENTITY` 用来设置创建后链接权限：

- 空值：不修改权限
- `tenant_editable`：组织内获得链接的人可编辑，推荐
- `tenant_readable`：组织内获得链接的人可阅读
- `anyone_editable`：互联网上获得链接的人可编辑，风险高且可能被企业策略拦截
- `anyone_readable`：互联网上获得链接的人可阅读

导入命令会创建两张表：

- `检测报告主表`
- `检测项目明细表`

当前导入阶段先用文本字段保存，`关联报告` 暂时保存为报告编号文本。后续接正式自动化流程时，再升级为多维表格关联字段。

正式生产使用时，不建议每次上传 PDF 都新建一个多维表格。推荐做法是提前建好固定的“检测报告主表”和“检测项目明细表”，之后管理员上传 PDF 只触发识别和写入固定表。

## 模板规则

模板规则在 `config/templates.yaml`。新增检测机构或新版式时，增加一条模板配置即可。规则主要分三类：

- `keywords`：用于判断 PDF 属于哪个模板。
- `fields`：报告主表字段的正则提取规则。
- `items`：检测项目明细的正则提取规则。

## 备注

- OCR 默认优先尝试 PaddleOCR；如果未安装 OCR 依赖，扫描件会解析失败并通知管理员。
- 飞书权限需要在多维表格里配置管理员、客服、研发三类角色的视图和字段权限。
- PDF 原件、`.env`、`output/` 解析结果、虚拟环境和缓存文件都已写入 `.gitignore`，不要提交到 GitHub。
