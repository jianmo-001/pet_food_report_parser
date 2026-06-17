# 服务器部署说明

这个项目第一版生产运行方式是 Python 常驻轮询，不依赖飞书自动化插件或公网 webhook。

## 运行逻辑

```text
管理员在飞书产品检测值宽表上传 PDF
↓
解析状态设为 未解析 / 待解析 / 留空
↓
服务器脚本定时扫描宽表
↓
下载 PDF 附件并解析
↓
保存 PDF 到服务器本地，完整数据写入 SQLite
↓
回填产品检测值宽表当前行
↓
写入详情页链接
↓
可选新增检测项目明细表
↓
解析状态改为 解析成功 / 解析失败
```

`output/` 不参与生产轮询，只用于本地查看解析结果或历史 CSV 导入。

## 服务器准备

推荐 Linux 服务器，Python 版本建议 3.11 及以上。

```bash
git clone https://github.com/jianmo-001/pet_food_report_parser.git
cd pet_food_report_parser
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev,ocr]"
cp .env.example .env
```

编辑 `.env`，至少填写：

```env
DRY_RUN=false
POLL_INTERVAL_SECONDS=60

FEISHU_APP_ID=你的企业自建应用 App ID
FEISHU_APP_SECRET=你的企业自建应用 App Secret
FEISHU_BITABLE_APP_TOKEN=多维表格 app_token
FEISHU_WIDE_TABLE_ID=产品检测值宽表 table_id
FEISHU_UPLOAD_TABLE_MODE=wide
FEISHU_ITEM_TABLE_ID=检测项目明细表 table_id，可选

DATABASE_URL=sqlite:///data/report_store.db
REPORT_PDF_DIR=data/reports/pdf
PUBLIC_BASE_URL=http://服务器公网IP
```

如果不需要飞书机器人通知，`FEISHU_BOT_WEBHOOK` 可以留空。

## 飞书表格字段要求

默认上传入口是 `产品检测值宽表`。建议字段：

```text
产品名称
PDF附件
解析状态
错误原因
PDF文件名
品牌名称
报告编号
替代报告编号
样品名称
样品编号
样品批号
样品规格
样品数量
样品状态
样品来源
客户名称
客户地址
检测机构
报告日期
样品接收日期
检测开始日期
检测结束日期
生产日期
生产商
检验类别
检测项目概述
判定标准
报告结论
备注
声明
解析模板
文本来源
检测项目数量
其他信息JSON
原文文本
详情页链接
粗蛋白
粗脂肪
水分
粗灰分
粗纤维
钙
总磷
钙磷比
钠
钾
镁
锌
铁
铜
锰
碘
硒
牛磺酸
淀粉
黄曲霉毒素B1
沙门氏菌
氯化物
维生素A
维生素D
维生素E
维生素B1
维生素B6
维生素B12
叶酸
胆碱
烟酸
泛酸
核黄素
净含量
未映射检测项目JSON
```

其中：

- `产品名称` 是飞书主字段/索引列，也是以后对比产品变化的入口。
- `PDF附件` 是附件字段，用于上传 PDF。
- `解析状态` 建议用单选字段，选项为 `未解析`、`待解析`、`解析中`、`解析成功`、`解析失败`、`疑似重复`。
- `错误原因` 建议用多行文本字段。
- `详情页链接` 建议用文本字段，用于打开服务器详情页。
- 日期字段如果设置为飞书日期类型，脚本会写入毫秒时间戳。
- 检测值列第一版建议用文本字段，避免丢失 `<`、`ND`、科学计数法和单位。

明细表建议字段：

```text
关联报告
序号
检测项目
单位
检测方法
检测结果
定量限|检出限
限值
单项结论
明细额外信息JSON
来源文本片段
```

建好空表并填写 `FEISHU_WIDE_TABLE_ID` 后，可以自动补齐宽表字段：

```bash
source .venv/bin/activate
python -m pdf_report_ingestor.cli ensure-wide-fields
```

## 手动测试

先运行一次：

```bash
source .venv/bin/activate
python -m pdf_report_ingestor.cli init-db
python -m pdf_report_ingestor.cli deploy-check --check-feishu
python -m pdf_report_ingestor.cli poll --once
```

看到类似下面输出表示命令跑通：

```text
processed=0
```

`processed=0` 只是表示当前没有待解析记录，不代表失败。要测试真实解析，需要在飞书主表上传 PDF，并把 `解析状态` 设为 `未解析` 或 `待解析`。

## 常驻运行

项目提供了启动脚本：

```bash
chmod +x scripts/run_poll.sh scripts/run_web.sh
scripts/run_poll.sh
```

这个脚本会自动进入项目根目录，检查 `.env` 和 `.venv`，然后执行：

```bash
.venv/bin/python -m pdf_report_ingestor.cli poll
```

详情页服务另开一个进程：

```bash
scripts/run_web.sh
```

详情页服务建议只监听本机 `127.0.0.1:8000`，不要在安全组里直接开放 8000。公网通过 Nginx 的 80/443 转发到本机 8000。

服务器 `.env` 里设置公网入口：

```bash
PUBLIC_BASE_URL=http://服务器公网IP
# 后续有域名和证书后改成：
# PUBLIC_BASE_URL=https://reports.example.com
```

浏览器打开 `http://服务器公网IP/report/{飞书record_id}` 可以查看详情页。正式使用时，飞书主表的 `详情页链接` 会自动填入这个公网入口。

Nginx 示例：

```nginx
server {
    listen 80;
    server_name 服务器公网IP;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

## 使用 systemd 常驻

在服务器上创建服务文件：

```bash
sudo nano /etc/systemd/system/pdf-report-poll.service
```

示例内容，注意把路径替换成你的服务器项目路径：

```ini
[Unit]
Description=PDF report Feishu poller
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
WorkingDirectory=/path/to/pet_food_report_parser
ExecStart=/path/to/pet_food_report_parser/scripts/run_poll.sh
Restart=always
RestartSec=10
User=你的服务器用户名

[Install]
WantedBy=multi-user.target
```

再创建 Web 服务：

```bash
sudo nano /etc/systemd/system/pdf-report-web.service
```

```ini
[Unit]
Description=PDF report detail web server
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
WorkingDirectory=/path/to/pet_food_report_parser
ExecStart=/path/to/pet_food_report_parser/scripts/run_web.sh
Restart=always
RestartSec=10
User=你的服务器用户名
Environment=HOST=127.0.0.1
Environment=PORT=8000

[Install]
WantedBy=multi-user.target
```

启动：

```bash
sudo systemctl daemon-reload
sudo systemctl enable pdf-report-poll
sudo systemctl enable pdf-report-web
sudo systemctl start pdf-report-poll
sudo systemctl start pdf-report-web
```

查看状态和日志：

```bash
sudo systemctl status pdf-report-poll
sudo journalctl -u pdf-report-poll -f
sudo systemctl status pdf-report-web
sudo journalctl -u pdf-report-web -f
```

## 更新代码

```bash
git pull
source .venv/bin/activate
pip install -e ".[dev,ocr]"
sudo systemctl restart pdf-report-poll
sudo systemctl restart pdf-report-web
```

## 常见问题

### 上传 PDF 后没有处理

检查：

- `.env` 里 `DRY_RUN=false`
- 主表 `PDF附件` 确实有附件
- `解析状态` 是 `未解析`、`待解析` 或空
- 应用已经被添加到对应多维表格，且有读取附件、读写多维表格权限
- `FEISHU_BITABLE_APP_TOKEN`、`FEISHU_REPORT_TABLE_ID`、`FEISHU_ITEM_TABLE_ID` 填的是同一个多维表格里的 ID

### 日期显示 1970

这是日期写入单位错误导致的。当前代码已经按飞书日期字段需要的毫秒时间戳写入。已经写错的旧记录需要把 `解析状态` 改回 `未解析` 后重新跑一次。

### 明细重复

当前第一版不会自动删除旧明细。如果同一条主表记录重复改成 `未解析` 并重新跑，可能会重复新增明细。正式使用前建议不要反复重跑同一行；后续可以补“重跑前删除旧明细”或“按报告编号去重”的逻辑。
