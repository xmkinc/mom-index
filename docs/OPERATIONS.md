# 宝妈指数运维手册

本文面向 `xmkinc/mom-index` 的维护者，覆盖 `data` 分支初始化、GitHub Pages 启用、定时与手动运行、降级行为、排障、安全和回滚。公开站点目标地址为 <https://xmkinc.github.io/mom-index/>。

## 1. 自动化边界

仓库有三条工作流：

| 工作流 | 触发 | 权限 | 持久化结果 |
| --- | --- | --- | --- |
| `CI` | PR、`master` 推送 | `contents: read` | 无 |
| `Refresh public data` | 每 6 小时、手动 | `contents: write` | 仅向 `data` 分支提交 `data/history.json`、`data/dashboard_data.json` |
| `Deploy GitHub Pages` | `master` 推送、成功刷新、手动 | `contents: read`、`pages: write`、`id-token: write` | GitHub Pages artifact/deployment |

公开刷新只运行 `python -m mom_index collect --sources guba`。它不进行小红书自动采集，不使用登录态、Cookie、浏览器配置或私有 API。`data/collection.json` 是被忽略的流水线中间文件：刷新工作流只把两个公开 JSON 复制到 `data` 分支，并在提交前校验暂存路径。

刷新和部署都使用 concurrency group，避免并发写入数据分支或交叉发布。刷新不会取消正在运行的前一轮任务；部署也不会中断正在发布的 Pages artifact。

## 2. 首次发布

### 2.1 合并前质量门

在 PR 分支安装固定依赖并执行完整检查：

```bash
python3.11 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements-dev.txt
python -m pip check
python -m pytest -q
python -m compileall -q mom_index scripts tests pipeline.py
python scripts/build_site.py --out _site
python scripts/check_site.py _site
python -c "import pathlib,yaml; [yaml.safe_load(p.read_text()) for p in pathlib.Path('.github/workflows').glob('*.yml')]; print('workflow yaml: OK')"
node --check frontend/assets/app.js
```

只有这些检查和设计复核通过后才合并到 `master`。

### 2.2 初始化 `data` 分支

`data` 分支是自动刷新唯一写入者和 LKG 存储。第一次启用工作流前，从已经包含 schema v2 种子数据的 `master` 创建它：

```bash
git fetch origin master
git ls-remote --exit-code --heads origin data
```

第二条命令退出码为 2 且没有输出，表示远端分支尚不存在，此时运行：

```bash
git push origin origin/master:refs/heads/data
```

如果 `git ls-remote` 已返回 `refs/heads/data`，不要覆盖或强推。检查分支上必须存在：

```text
data/history.json
data/dashboard_data.json
```

同时必须不存在 `data/collection.json`。不要在 `data` 分支手工制造“当前”读数；实时数据只能由刷新工作流生成。

### 2.3 启用 GitHub Pages

1. 打开仓库 `Settings` → `Pages`。
2. 在 `Build and deployment` 的 `Source` 中选择 `GitHub Actions`。
3. 确认仓库 `Actions` 已启用，默认分支为 `master`。
4. 打开 `Actions` → `Deploy GitHub Pages` → `Run workflow`，保持 `code_ref=master`、`data_ref=data`。
5. 运行成功后访问 <https://xmkinc.github.io/mom-index/>，确认页面能加载四个板块、来源状态、更新时间和降级/过期提示。

Pages 环境可以设置 required reviewers；如果启用，部署 job 会等待环境审批，这是仓库策略而不是程序故障。

## 3. 正常运行

### 3.1 周期

刷新 cron 为：

```text
17 */6 * * *
```

即 UTC 00:17、06:17、12:17、18:17，每天最多四次。北京时间对应 08:17、14:17、20:17、次日 02:17。GitHub Actions 的 schedule 可能延迟，页面还会用浏览器当前时间重新判断是否超过 12 小时，因此调度器停止也会显示过期。

每轮刷新执行：

```text
checkout 固定 master SHA + checkout data 分支
→ 把 data 分支的 LKG 复制到代码工作区
→ collect --sources guba
→ build
→ validate
→ build_site + check_site + node --check
→ 只暂存两个公开 JSON
→ 有变化才提交并推送 data
→ workflow_run 触发 Pages 部署
```

### 3.2 手动刷新

网页：`Actions` → `Refresh public data` → `Run workflow`，分支选择 `master`。

GitHub CLI：

```bash
gh workflow run refresh-data.yml --repo xmkinc/mom-index --ref master
gh run list --repo xmkinc/mom-index --workflow refresh-data.yml --limit 5
```

刷新结束后，成功的 `workflow_run` 会触发部署；不需要提交空 commit。

### 3.3 手动部署

网页：`Actions` → `Deploy GitHub Pages` → `Run workflow`，填写代码 ref 和数据 ref。常规值：

```text
code_ref = master
data_ref = data
```

GitHub CLI：

```bash
gh workflow run deploy.yml \
  --repo xmkinc/mom-index \
  --ref master \
  -f code_ref=master \
  -f data_ref=data
```

手动 ref 可以是分支、tag 或完整 commit SHA。Actions checkout 后会在 job summary 记录实际代码 SHA 和数据 SHA，便于重现发布输入。

## 4. 可观测性与成功判定

列出和查看运行：

```bash
gh run list --repo xmkinc/mom-index --workflow ci.yml --limit 10
gh run list --repo xmkinc/mom-index --workflow refresh-data.yml --limit 10
gh run list --repo xmkinc/mom-index --workflow deploy.yml --limit 10
gh run view <run-id> --repo xmkinc/mom-index --log-failed
```

刷新 job 日志应出现以下阶段：

- 股吧来源的 `mode=live` 或明确的 `mode=unavailable`；
- schema v2 验证成功；
- `check_site: OK`；
- 仅两个允许路径进入暂存区；
- 有变化时生成 `chore(data): refresh public dashboard` commit，无变化时明确报告 no data commit。

“工作流绿色”不等于“股吧采集成功”。判断实时成功必须同时查看公开 payload：

```bash
curl -fsSL https://xmkinc.github.io/mom-index/data/dashboard_data.json \
  | python -m json.tool
```

重点字段：

- `sources[].mode`：股吧应为 `live`；失败时为 `unavailable`。
- `sources[].collected_at`：仅成功来源有采集时间。
- `freshness.last_success_at`：最近一次完整四板块成功时间。
- `freshness.is_stale`：超过 12 小时或从未成功时为 `true`。
- `warnings`：逐来源错误和过期原因。
- `record_count`、`latest`：LKG 记录数量和最近成功读数。

## 5. 降级和失败语义

### 股吧请求失败或零有效帖子

采集器返回 `unavailable`，不产生伪造读数。`build` 保留 `data` 分支已有的历史与 `last_success_at`，更新公开来源状态和警告；只要 schema、站点检查和安全检查通过，这个降级 payload 可以提交并部署。页面继续展示 LKG，同时显示降级；超过 12 小时后显示过期。

### schema、构建或站点检查失败

刷新 job 失败，不会提交数据。部署 job 在上传 artifact 前失败，GitHub Pages 继续提供上一次成功部署。这类失败不能通过手工编辑 JSON 绕过，应在代码 PR 中修复并重新运行全部质量门。

### Pages 部署失败

构建成功但 `deploy-pages` 失败时，查看 `github-pages` environment 和 Pages 设置。旧部署通常仍可访问；修复配置后手动重跑部署。

## 6. 排障

### `data` 分支 checkout 失败

确认分支存在且 GitHub Actions 可读：

```bash
git ls-remote --exit-code --heads origin data
```

若首次初始化，按 2.2 节创建。若分支存在，不要强推；检查仓库 Actions 权限是否允许工作流读写 contents。

### 刷新不能 push

在 `Settings` → `Actions` → `General` 检查 `Workflow permissions`。刷新工作流声明 `contents: write`，仓库策略仍可能把 `GITHUB_TOKEN` 限制为只读。只需允许该内置 token 写仓库内容；不要创建或粘贴个人访问令牌。

同时检查 `data` 分支保护规则是否允许 `github-actions[bot]` 通过指定工作流更新。不要关闭 `master` 保护来解决数据分支问题。

### 股吧持续 `unavailable`

先查看 refresh 日志中的每板块错误和公开 payload 的 `warnings`。常见原因包括：

- GitHub runner 出口网络或地域被公开站点限制；
- 请求超时或临时 429/5xx；
- 股吧 HTML 行结构变化导致零有效帖子。

工作流会重试可重试的网络错误，但不会把零帖子算作成功。若持续发生，应提交新的采集器修复或设计备用公开来源；不要把本地模拟数据切换成公开 `live`。

### 站点 404 或资源路径错误

确认 Pages Source 为 `GitHub Actions`，最近一次 deploy 绿色，artifact 根目录含 `index.html`。本地复现：

```bash
python scripts/build_site.py --out _site
python scripts/check_site.py _site
python -m http.server 8765 --directory _site
```

资源必须使用相对路径，不能硬编码 `/mom-index/` 或 CDN URL。

### YAML 或依赖失败

```bash
python -m pip install -r requirements-dev.txt
python -m pip check
python -c "import pathlib,yaml; [yaml.safe_load(p.read_text()) for p in pathlib.Path('.github/workflows').glob('*.yml')]; print('workflow yaml: OK')"
```

依赖版本只在 `requirements.txt` 和 `requirements-dev.txt` 更新；更新后必须经 PR 和完整测试。

## 7. 回滚

### 立即回滚站点输入，不改历史

找到最近的良好代码和数据 commit：

```bash
git fetch origin master data
git log --oneline origin/master
git log --oneline origin/data -- data/history.json data/dashboard_data.json
```

用完整 SHA 手动部署：

```bash
gh workflow run deploy.yml \
  --repo xmkinc/mom-index \
  --ref master \
  -f code_ref=<good-master-sha> \
  -f data_ref=<good-data-sha>
```

这会重新构建并检查旧输入，不改 `master` 或 `data`。确认稳定后，再决定是否永久回退。

### 永久回退错误数据 commit

不要改写 `data` 分支历史。使用临时分支 revert：

```bash
git fetch origin data
git switch --create data-rollback --track origin/data
git revert <bad-data-commit-sha>
git push origin HEAD:data
```

随后手动部署 `code_ref=master`、`data_ref=data`。完成后删除本地临时分支。禁止 force-push。

### 永久回退代码

在新分支对错误代码 commit 执行 `git revert`，通过 PR、CI 和设计复核合并到 `master`；不要直接写默认分支。Pages 在新部署失败时仍保留上一次成功 artifact。

## 8. 安全检查清单

- CI 只有 `contents: read`；刷新只有 `contents: write`；部署只拥有 `contents: read`、`pages: write`、`id-token: write`。
- 不使用 `pull_request_target`，不以写 token 执行 fork 提交。
- 所有第三方 Actions 使用固定主版本：checkout v4、setup-python v5、Pages configure v5、upload v3、deploy v4。
- 公开刷新只采集无需登录的股吧页面。
- `collection.json`、原始帖子、作者身份、Cookie、token、代理凭据和本地浏览器状态不进入 Git 或 Pages artifact。
- `scripts/check_site.py` 在发布前验证 schema、相对路径、vendored Chart.js、来源诚实性和常见秘密模式。
- 任何权限扩大、来源变化、schema 变化或默认启用模拟数据都必须走新的架构决策和 PR 审查。
