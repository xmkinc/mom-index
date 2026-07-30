# 👩‍👧 宝妈指数（Mom Index）

宝妈指数是一个静态、可审计的散户情绪观察面板。它用确定性的关键词规则分析东方财富股吧公开帖子，分别展示纳斯达克、黄金、CPO 通信和半导体四个板块的情绪热度。指数越高，表示样本中的新手参与和极端情绪越集中；它不是涨跌预测模型。

公开地址：<https://xmkinc.github.io/mom-index/>

> 本项目仅用于学习、研究和数据工程演示，不构成投资建议。数据可能延迟、缺失或因公开站点限制而不可用，请勿据此进行交易。

## 当前数据承诺

面板使用 schema v2，每次输出都会公开生成时间、展示时区、各数据源模式、最后成功时间、过期状态和警告。采集失败时不会伪造新读数：系统保留最后一次成功历史（last-known-good，LKG），把股吧标记为 `unavailable`，并在页面显示降级或过期状态。

| 数据源 | 公开定时任务 | 公开模式 | 说明 |
| --- | --- | --- | --- |
| 东方财富股吧 | 启用，每 6 小时一次 | `live` 或 `unavailable` | 无需登录的公开页面；每次读取四个板块列表页 |
| 小红书 | 禁用 | `unavailable` | 公开部署不登录、不读取本地浏览器状态，也不把示例数据冒充实时数据 |
| 显式模拟样本 | 禁用 | `simulated` | 仅供本地测试，必须主动传入 `--allow-simulated`，输出始终带模拟标记 |

仓库保留显式选择的本地小红书适配边界，但它不属于公开定时链路；未在本地明确启用时，公开 payload 始终把该来源标为 `unavailable`。任何本地来源都不能改变 GitHub Actions 的股吧单来源默认值。

公开产物只保留汇总指标、最多五条代表性标题和公开来源链接；不发布作者身份、关注者数据、原始帖子集合、Cookie 或凭据。

## 指数方法

分类器是确定性的关键词规则引擎，不是 LLM。垃圾帖先被排除；其余帖子依据身份自述、知识求助、决策依赖、情绪、跟风行为和专业信号计算新手分数及买卖意图。重复帖子按稳定 ID 去重，同一输入会得到同一结果。

主指数公式版本为 `1.1`：

```text
宝妈指数 =
  小白占比 × 0.40 +
  小白平均强度 × 0.25 +
  情绪极端度 × 0.20 +
  纯小白占比 × 0.15
```

指数范围为 0–100：

| 区间 | 页面解释 |
| --- | --- |
| 0–20 | 极度冷清 |
| 20–40 | 正常区间 |
| 40–60 | 开始升温 |
| 60–75 | 高度警惕 |
| 75–100 | 极度狂热 |

页面还展示买入和卖出子指数。讨论活跃度作为独立观察值呈现，不参与主指数加权；当存在买入样本但卖出样本为零时，买卖比用 `null` 表达并在页面显示为 `∞`，不会用虚构分母计算。

## 快速开始

需要 Python 3.11+。运行时依赖和开发依赖都已固定版本：

```bash
git clone https://github.com/xmkinc/mom-index.git
cd mom-index
python3.11 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements-dev.txt
```

执行一次公开股吧采集、构建和验证：

```bash
python -m mom_index collect --sources guba --out data
python -m mom_index build --data data --out data/dashboard_data.json
python -m mom_index validate data/dashboard_data.json
```

采集网络失败时，第一条命令仍会保存明确的 `unavailable` 状态；第二条命令复用现有 LKG 历史并生成可验证的降级页面数据。中间文件 `data/collection.json` 只在本地流程中使用，已被 Git 忽略，绝不会进入公开数据分支或站点。

构建并预览静态站点：

```bash
python scripts/build_site.py --out _site
python scripts/check_site.py _site
python -m http.server 8765 --directory _site
```

打开 <http://localhost:8765/>。所有运行时资源均为相对路径，Chart.js 已随仓库提供，不依赖 CDN，因此站点可部署在 `/mom-index/` 子路径。

如需本地演示模拟状态，请使用独立临时目录，避免混入正式 LKG：

```bash
python -m mom_index all --sources guba --allow-simulated --data /tmp/mom-index-demo
python -m mom_index validate /tmp/mom-index-demo/dashboard_data.json
```

## 测试与质量门

提交前运行与 CI 相同的命令：

```bash
python -m pip check
python -m pytest -q
python -m compileall -q mom_index scripts tests pipeline.py
python scripts/build_site.py --out _site
python scripts/check_site.py _site
python -c "import pathlib,yaml; [yaml.safe_load(p.read_text()) for p in pathlib.Path('.github/workflows').glob('*.yml')]; print('workflow yaml: OK')"
node --check frontend/assets/app.js
```

CI 在 pull request 和 `master` 推送上运行，只有 `contents: read` 权限。测试覆盖分类、去重、评分边界、买卖比、时区、股吧行级解析、存储/LKG、schema 导出和强制失败降级路径。

## 命令与目录

稳定 CLI：

```text
python -m mom_index collect [--sources guba] [--allow-simulated] [--out data/]
python -m mom_index build [--data data/] [--out data/dashboard_data.json]
python -m mom_index validate <payload.json>
python -m mom_index all [--sources guba] [--data data/]
```

主要目录：

```text
mom_index/
  collectors/        公开采集器与显式来源状态
  analysis/          纯函数分类与评分
  storage.py         LKG 历史、同日替换与原子写入
  export.py          schema v2 隐私过滤导出
  cli.py             collect / build / validate / all
schema/               dashboard.schema.json
frontend/             静态页面与 vendored Chart.js
scripts/              站点组装和发布前检查
tests/                pytest 测试与固定样本
data/                 公开 history.json 和 dashboard_data.json
.github/workflows/    CI、数据刷新和 Pages 部署
docs/OPERATIONS.md    初始化、监控、故障与回滚手册
```

`pipeline.py` 仅保留为旧命令兼容入口，新自动化统一调用 `python -m mom_index`。`frontend/data/` 和 `_site/` 都是构建输出，不提交到 Git。

## 自动化与部署

- `ci.yml`：在 PR 和 `master` 推送时执行依赖检查、pytest、compileall、站点构建/检查、JavaScript 语法和工作流 YAML 解析。
- `refresh-data.yml`：每天 UTC 00:17、06:17、12:17、18:17 运行，也支持手动触发；它只采集股吧，只向 `data` 分支提交两个公开 JSON。
- `deploy.yml`：在 `master` 推送、成功的数据刷新或手动触发后，从指定代码提交和数据提交重新构建、检查并通过 GitHub Pages 官方 Actions 发布。

首次创建 `data` 分支、启用 Pages、手动触发、监控和回滚的完整步骤见 [运维手册](docs/OPERATIONS.md)。

## 已知局限

- GitHub 托管 runner 可能被股吧的网络策略或地域限制拦截；这种情况会诚实显示为降级，而不是实时成功。
- 股吧 HTML 结构变化可能造成零有效帖子；零帖子被视为失败，不会覆盖最后成功指数。
- 关键词规则无法理解所有语境，可能漏判反讽、隐含表达或新词。
- 项目没有行情回测，指数与未来价格之间不存在经验证的因果或预测关系。
- 新部署在积累足够多的真实记录前，趋势图会显示“历史数据不足”。

## License

[MIT](LICENSE)
