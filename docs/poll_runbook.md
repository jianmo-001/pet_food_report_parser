# poll 轮询服务运维手册

poll 是生产主进程：定时扫描飞书「产品检测值宽表」里待解析的记录 → 下载 PDF → 解析 → 回填宽表 → 自动归档到共享文件夹。本手册只讲 poll 的运维；Nginx/详情页 web 见 `server_deploy.md`。

## 一、首次上线（安全顺序，别跳）

> 关键：`DRY_RUN=true` 时 poll **直接空转什么都不做**，没法用它试跑。所以测试一律用 `DRY_RUN=false`，靠下面的分步开关来控风险。

1. 装好环境、填好 `.env`（见 `server_deploy.md`）。确认：
   - `DRY_RUN=false`
   - `FEISHU_ARCHIVE_ENABLED=false`  ← 第一步先**关归档**
2. 跑一次连通性检查和单轮：
   ```bash
   source .venv/bin/activate
   python -m pdf_report_ingestor.cli init-db
   python -m pdf_report_ingestor.cli deploy-check --check-feishu
   python -m pdf_report_ingestor.cli poll --once
   ```
3. 在飞书宽表上传 1 份 PDF、状态设「未解析」，再 `poll --once`。确认：解析成功、宽表字段回填正确、详情页链接能打开。**此时归档是关的,不会动共享文件夹。**
4. 一切正常后，`.env` 改 `FEISHU_ARCHIVE_ENABLED=true`，再上传 1 份、`poll --once`。确认：文件进了**对的产品文件夹**、宽表「归档路径」「归档文件链接」都写对。
5. 没问题，再交给 systemd 长跑（下一节）。

## 二、装成 systemd 守护服务

```bash
# 1. 复制单元文件，按需改 WorkingDirectory / User
sudo cp deploy/pdf-report-poll.service /etc/systemd/system/
sudo nano /etc/systemd/system/pdf-report-poll.service

# 2. 启用并启动
sudo systemctl daemon-reload
sudo systemctl enable pdf-report-poll
sudo systemctl start pdf-report-poll
```

## 三、日常操作

```bash
sudo systemctl status pdf-report-poll        # 看运行状态
sudo systemctl restart pdf-report-poll        # 重启（改完 .env / 规则后用）
sudo systemctl stop pdf-report-poll           # 停
sudo journalctl -u pdf-report-poll -f         # 实时日志
sudo journalctl -u pdf-report-poll --since "1 hour ago"   # 近一小时日志
```

每轮日志会打印 `poll cycle finished, processed=N`，N 是本轮处理的记录数。

## 四、监控要看什么

- **服务存活**：`systemctl is-active pdf-report-poll` 应为 `active`。可挂到你们的监控/告警。
- **解析失败**：宽表里「解析状态=解析失败」+「错误原因」。想要主动告警就在 `.env` 填 `FEISHU_BOT_WEBHOOK`，失败会推飞书群。
- **归档失败/未匹配**：看记录的「归档错误」字段，以及项目根目录 `output/archive_unmatched.csv` 清单（哪些 PDF 没匹配到文件夹、需人工归或加规则）。
- **磁盘**：`REPORT_PDF_DIR` 会持续存 PDF，注意别撑满。

## 五、改配置后怎么生效

- 改 `.env` 或 `config/archive_rules.yaml`：`sudo systemctl restart pdf-report-poll`。
- 拉新代码：
  ```bash
  git pull
  source .venv/bin/activate && pip install -e ".[dev,ocr]"
  sudo systemctl restart pdf-report-poll
  ```

## 六、常见问题

| 现象 | 排查 |
|---|---|
| 上传 PDF 没反应 | `DRY_RUN=false`？附件字段有附件？状态是未解析/待解析/空？应用对宽表有读写+附件权限？ |
| 一直重启/起不来 | `journalctl -u pdf-report-poll -n 50` 看报错；多半是 `.env` 缺值或 `.venv` 没装好 |
| 解析成功但没归档 | `FEISHU_ARCHIVE_ENABLED=true`？`FEISHU_ARCHIVE_ROOT_TOKEN` 填了？看「归档错误」字段 |
| 归档进了未匹配清单 | 新产品文件名没有可识别的代号/类目词 → 往 `config/archive_rules.yaml` 加一条规则，用 `scripts/validate_archive_router.py` 复跑验证 |
| 扫描件解析失败 | 服务器没装 OCR：`pip install -e ".[dev,ocr]"` |

## 七、单实例约束

poll 只能起**一个实例**。多开会重复处理同一条记录。systemd 单元已保证单实例；别再手动 `run_poll.sh` 叠加跑。
