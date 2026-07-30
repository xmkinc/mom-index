# 👩‍👧 宝妈指数（Mom Index）

宝妈指数是一个静态、可审计的散户情绪观察面板。它用确定性的关键词规则分析东方财富股吧公开帖子，也支持在本地显式导入经过清洗的小红书公开帖子。面板分别展示纳斯达克、黄金、CPO 通信和半导体四个板块的社交指数、买卖语言证据、客观样本质量和独立市场背景。指数越高，只表示样本中的新手参与和极端表达越集中；它不是涨跌预测模型。

公开地址：<https://xmkinc.github.io/mom-index/>

> 本项目仅用于学习、研究和数据工程演示，不构成投资建议。数据可能延迟、缺失或因公开站点限制而不可用，请勿据此进行交易。

## 当前数据承诺

面板使用 schema v3，每次输出都会公开生成时间、展示时区、各数据源模式、最后成功时间、过期状态、样本质量、市场背景来源和警告。采集失败时不会伪造新读数：系统保留最后一次成功历史（last-known-good，LKG），把失败来源标记为 `unavailable`，并在页面显示降级或过期状态。存储层会把旧 schema v2 历史加法迁移为 v3；前端也能明确展示旧 v2 payload，但公开构建产物必须是 v3，未知版本会被拒绝。

| 数据源 | 公开定时任务 | 公开模式 | 说明 |
| --- | --- | --- | --- |
| 东方财富股吧 | 启用，每 6 小时一次 | `live` 或 `unavailable` | 无需登录的公开页面；每次读取四个板块列表页 |
| 小红书 | 禁用 | `unavailable` | 公开部署不登录、不读取本地浏览器状态；本地可用 `--xhs-import` 显式导入已清洗 JSON/JSONL，模式为 `imported` |
| 显式模拟样本 | 禁用 | `simulated` | 仅供本地测试，必须主动传入 `--allow-simulated`，输出始终带模拟标记 |
| 市场背景 | 禁用 | `unavailable` | 本地可用 `--market-import` 传入四板块行情快照；它只作独立背景展示，不进入社交指数公式 |

仓库保留两条显式选择的本地小红书边界：推荐的清洗文件导入，以及旧的 `xhs-rnote` 本地适配器。它们都不属于公开定时链路；未在本地明确启用时，公开 payload 始终把该来源标为 `unavailable`。任何本地来源和行情快照都不能改变 GitHub Actions 的股吧单来源默认值。

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

每个板块还输出样本质量模型 `1.0`，只根据可观测字段计算：

- 有效样本量；
- 仅标题样本比例；
- 各平台样本数；
- 分类器证据覆盖率；
- 72 小时窗口内的已知时间样本比例；
- 发布时间未知比例。

样本量小于 30、仅标题比例大于 80%，或分类证据覆盖率低于 30% 时，置信度为 `low`。只有样本量至少 60、仅标题比例不高于 40%、证据覆盖率至少 50%，且已知时间窗口内比例至少 60% 时才为 `high`；其余为 `medium`。每个未通过的门槛都有稳定原因代码。时间缺失或无法解析时一律记为未知，不进行猜测。

市场背景按配置的四个 ETF 参考标的展示 1 日、5 日和 20 日收益、行情截至时间、导入时间和来源标签。行情可以缺失或降级，但绝不会流入公式版本 `1.1`，也不用于解释社交指数的原因或预测后续价格。

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

### 本地导入已清洗的小红书数据

导入文件可以是 JSON 数组、按四个板块分组的 JSON 对象或 JSONL。每条记录只允许以下字段：

```text
id, title, content, url, sector, published_at, collected_at
```

`url` 必须是 HTTPS 小红书域名，`sector` 必须是配置的四个板块之一，时间必须带时区。任何作者身份、用户资料、关注数据、会话字段、凭据字段或疑似秘密值都会使整次导入失败关闭；普通的单条格式错误会被明确记录，且不会静默删除。建议始终使用独立数据目录：

```bash
python -m mom_index collect \
  --sources guba \
  --xhs-import /absolute/path/to/sanitized-xhs.jsonl \
  --out /tmp/mom-index-local
python -m mom_index build \
  --data /tmp/mom-index-local \
  --out /tmp/mom-index-local/dashboard_data.json
python -m mom_index validate /tmp/mom-index-local/dashboard_data.json
```

不要把导入文件、`collection.json` 或任何原始记录提交到仓库。`--xhs-import` 与旧的 `xhs-rnote` 来源互斥，避免同一来源出现两个相互冲突的状态。

### 本地导入市场背景

市场快照是 schema v1 JSON，必须包含来源标签、带时区的导入时间，以及四个板块的固定参考代码/名称、带时区的行情截至时间和至少一个 `1d`、`5d`、`20d` 收益窗口。它只对当前这次构建生效，不会持久化为采集来源：

```bash
python -m mom_index build \
  --data /tmp/mom-index-local \
  --market-import /absolute/path/to/market-snapshot.json \
  --out /tmp/mom-index-local/dashboard_data.json
python -m mom_index validate /tmp/mom-index-local/dashboard_data.json
```

文件缺失、JSON 无效或参考标的不匹配时，构建仍会完成，但 `market_context.status` 为 `unavailable` 并带可见警告。使用 `all` 命令时也可以同时显式传入 `--xhs-import` 和 `--market-import`。

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

CI 在 pull request 和 `master` 推送上运行，只有 `contents: read` 权限。测试覆盖分类、去重、评分边界、买卖比、时区、股吧行级解析、样本质量、清洗导入、行情快照、存储/LKG、schema 导出和强制失败降级路径。

## 命令与目录

稳定 CLI：

```text
python -m mom_index collect [--sources guba] [--xhs-import PATH] [--allow-simulated] [--out data/]
python -m mom_index build [--data data/] [--market-import PATH] [--out data/dashboard_data.json]
python -m mom_index validate <payload.json>
python -m mom_index all [--sources guba] [--xhs-import PATH] [--market-import PATH] [--data data/]
```

主要目录：

```text
mom_index/
  collectors/        公开采集器、清洗导入与显式来源状态
  analysis/          纯函数分类、评分与样本质量
  market/            本地市场快照验证和降级边界
  storage.py         LKG 历史、同日替换与原子写入
  export.py          schema v3 隐私过滤导出
  cli.py             collect / build / validate / all
schema/               dashboard、XHS 导入与市场快照 schema
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
- 小红书和市场快照的公开定时采集仍未启用；本地导入是否及时、完整取决于操作者提供的清洗文件。
- 样本质量是对数据覆盖和可解释证据的客观门槛，不等同于分类结论或市场结论的正确概率。
- 项目没有行情回测，指数与未来价格之间不存在经验证的因果或预测关系。
- 新部署在积累足够多的真实记录前，趋势图会显示“历史数据不足”。

## License

[MIT](LICENSE)
