# 双仓库架构计划

> 本计划将 escaping 打造成唯一的代码维护仓库，通过自动化工作流同步到 geoqiao.github.io。

## 背景

**当前问题：**
- 本地代码推送到 `geoqiao.github.io`，而非 `escaping`
- `escaping` 长期未更新，代码落后
- 维护者需要管理两份代码，容易混乱

**目标：**
- 在 `escaping` 维护所有代码
- Issues 依然存放在 `geoqiao.github.io`
- Issues 更新后自动触发部署
- 用户可以从 `escaping` fork 并使用

---

## 仓库职责

| 仓库 | 作用 | 存放内容 |
|---|---|---|
| `escaping` | 主开发仓库，所有代码在这里维护 | 源代码、workflows、templates |
| `geoqiao.github.io` | Issues 存放 + GitHub Pages 部署 | Issues（博客文章）、接收 trigger.yml |

---

## 架构图

```
┌─────────────────────────────────────────────────────────────┐
│ escaping (主仓库，所有代码在这里维护)                     │
│                                                             │
│ ├── .github/workflows/                                     │
│ │   ├── gen_site.yml    ✅ 在这里运行                      │
│ │   ├── trigger.yml     ❌ 不运行，只同步到 geoqiao        │
│ │   └── sync.yml        ✅ 检测 trigger.yml 变化并同步     │
│ │                                                             │
│ │   └── (其他源代码文件)                                      │
└─────────────────────────────────────────────────────────────┘
                              │
                              │ sync.yml 自动同步
                              ▼
┌─────────────────────────────────────────────────────────────┐
│ geoqiao.github.io (Issues 存放 + GitHub Pages)              │
│                                                             │
│ ├── Issues (博客文章)                                       │
│ └── .github/workflows/                                      │
│     └── trigger.yml    ✅ 接收同步过来的 trigger             │
│                                                             │
│     (当 issues 更新/编辑时触发，发送 dispatch 到 escaping)  │
└─────────────────────────────────────────────────────────────┘
                              │
                              │ repository_dispatch
                              ▼
┌─────────────────────────────────────────────────────────────┐
│ escaping (接收 dispatch)                                 │
│                                                             │
│ gen_site.yml 被触发:                                        │
│   1. 读取 geoqiao.github.io 的 issues                       │
│   2. 生成静态网站                                           │
│   3. 部署到 GitHub Pages (geoqiao.github.io)                │
└─────────────────────────────────────────────────────────────┘
```

---

## 工作流程

### 流程 1: Issues 更新自动部署

```
1. geoqiao.github.io 的 issue 被创建/编辑
        ↓
2. geoqiao.github.io 的 trigger.yml 检测到事件
        ↓
3. trigger.yml 发送 repository_dispatch 到 escaping
        ↓
4. escaping 的 gen_site.yml 被触发
        ↓
5. gen_site.yml:
   - 读取 geoqiao.github.io 的 issues
   - 生成静态文件
   - 部署到 GitHub Pages
```

### 流程 2: 维护者更新 trigger.yml

```
1. 维护者在 escaping 修改 .github/workflows/trigger.yml
        ↓
2. escaping 的 sync.yml 检测到 trigger.yml 变化
        ↓
3. sync.yml 自动将 trigger.yml 推送到 geoqiao.github.io
```

### 流程 3: 普通用户使用

```
1. 用户 Fork escaping
2. 配置自己的 config.yaml (指向自己的 issues 仓库)
3. 设置 G_T token
4. Issues 更新 → 自动部署到自己的 GitHub Pages
```

---

## 实施步骤

### Step 1: 准备 G_T Token

确认 Token 权限：
- ✅ `repo` - 读取 issues
- ✅ `workflow` - 触发 Actions
- 已在 geoqiao.github.io 的 Secrets 中

### Step 2: 修改 escaping 的 gen_site.yml

添加 `repository_dispatch` 触发器：

```yaml
name: Generate Github_blog site

on:
  workflow_dispatch:
  repository_dispatch:
    types: [issue_update]
  push:
    branches:
      - main
  # ...
```

### Step 3: 创建 sync.yml

在 `.github/workflows/sync.yml`：

```yaml
name: Sync Trigger to Geoqiao Pages

on:
  push:
    paths:
      - '.github/workflows/trigger.yml'
    branches:
      - main

jobs:
  sync:
    runs-on: ubuntu-latest
    steps:
      - name: Checkout
        uses: actions/checkout@v4

      - name: Push trigger.yml to geoqiao.github.io
        env:
          GH_TOKEN: ${{ secrets.G_T }}
        run: |
          git clone https://github.com/geoqiao/geoqiao.github.io.git _pages
          mkdir -p _pages/.github/workflows
          cp .github/workflows/trigger.yml _pages/.github/workflows/
          cd _pages
          git config user.name "github-actions"
          git config user.email "github-actions@github.com"
          git add .
          git commit -m "sync: update trigger.yml"
          git push
```

### Step 4: 创建 trigger.yml

在 `.github/workflows/trigger.yml`：

```yaml
name: Trigger Deploy

on:
  issues:
    types: [opened, edited]
  issue_comment:
    types: [created, edited]

jobs:
  trigger:
    runs-on: ubuntu-latest
    steps:
      - name: Trigger escaping
        run: |
          curl -L -X POST \
            -H "Accept: application/vnd.github+json" \
            -H "Authorization: Bearer ${{ secrets.G_T }}" \
            https://api.github.com/repos/geoqiao/escaping/dispatches \
            -d '{"event_type":"issue_update"}'
```

### Step 5: 将 trigger.yml 同步到 geoqiao.github.io

运行一次 sync.yml（手动或自动），将初始的 trigger.yml 推送到 geoqiao.github.io。

### Step 6: 修改本地 Git Remote

```bash
# 查看当前 remote
git remote -v

# 修改 origin 为 escaping
git remote set-url origin git@github.com:geoqiao/escaping.git

# 确认
git remote -v

# 推送
git push origin main
```

---

## 文件变更清单

| 操作 | 文件 | 说明 |
|---|---|---|
| 新增 | `.github/workflows/sync.yml` | 检测 trigger.yml 变化并同步 |
| 新增 | `.github/workflows/trigger.yml` | 监听 issues 事件并发送 dispatch |
| 修改 | `.github/workflows/gen_site.yml` | 添加 repository_dispatch 触发器 |
| 无变更 | `templates/` | 主题文件不变 |
| 无变更 | `src/` | 源代码不变 |
| 无变更 | `config.yaml` | 配置不变 |

---

## Token 配置检查清单

- [ ] `G_T` token 有效期有效
- [ ] `G_T` 有 `repo` scope
- [ ] `G_T` 已添加到 geoqiao.github.io 的 Secrets
- [ ] `G_T` 已添加到 escaping 的 Secrets（需要新增）

---

## 用户使用说明

### 对于想搭建自己博客的用户

1. Fork `escaping`
2. 在自己的 GitHub Pages 仓库（或任何存放 Issues 的仓库）发布 Issues
3. 配置 `config.yaml` 中的 `github.repo` 为你的仓库地址
4. 在仓库 Secrets 中添加 `G_T` token
5. Issues 更新后自动部署

### 对于贡献代码的开发者

1. Fork `escaping`
2. 修改代码并提交 PR
3. PR merge 后，workflow 自动测试和部署

---

## 回滚计划

如果出现问题：
1. 可以手动在 geoqiao.github.io 直接修改 trigger.yml
2. 或者禁用 sync.yml 的自动同步
3. 紧急情况下可以直接在 geoqiao.github.io 修改 workflow

---

## 确认清单

- [ ] 理解双仓库架构
- [ ] Token 权限确认
- [ ] 计划文档已阅读
- [ ] 同意开始执行
