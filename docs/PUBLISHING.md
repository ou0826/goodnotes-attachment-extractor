# 发布到 GitHub 指南（新手版）

这份文档写给第一次开源的人。按顺序做，大约 30 分钟可以把项目发布到 GitHub。
法律部分只是常见做法的说明，**不构成法律意见**；涉及学校职务成果、资助项目或商业
合作时，请先咨询学校相关部门或律师。

---

## 一、发布前必须确认的三件事

### 1. 版权归属

确认代码是你个人独立开发，还是在职务范围内、使用学校或单位资源完成：

- **个人独立开发**：可以直接用本仓库的 MIT 许可证发布，版权人写你的名字。
- **学校、单位或合作项目**：先取得权利人的书面同意，再把 LICENSE 中的版权人
  改为相应单位，并在 README 中说明。

拿不准时，先问学校科技处/资产处或导师，不要直接发布。

### 2. 有没有不该公开的内容

**绝对不要上传**：

| 文件 | 原因 |
| --- | --- |
| 证书、签章页、代码文档等申请材料 | 含身份证件、签名等个人信息，且与开源代码重复 |
| 任何 `.goodnotes` 文件 | 含真实笔记、录音、图片 |
| `GoodNotes附件提取.exe` | 二进制产物，应通过 Releases 分发 |
| 日志 `*.log` | 可能含个人路径和文件名 |

本仓库的 `.gitignore` 已经排除了 `.goodnotes`、日志、`dist/`、`build/` 等，
但**已经存在于工作区的文件仍会被 `git add` 加进去**，所以第一次 `git add` 前请
用 `git status` 检查一遍。

### 3. 选哪个许可证

| 许可证 | 特点 | 适合场景 |
| --- | --- | --- |
| **MIT**（本仓库默认） | 最短、最宽松，保留版权声明即可商用 | 工具类项目，希望被广泛使用 |
| Apache-2.0 | 比 MIT 多专利授权和商标条款，文本更长 | 有专利风险或企业参与 |
| GPL-3.0 | 衍生作品必须同样开源 | 不希望被闭源商用 |

对这个小工具，MIT 足够，也最容易理解。**不要**在没有律师的情况下自创许可证文本。

本仓库已经包含：

- `LICENSE`：MIT 全文，版权人为 `Xiangyu`；
- `NOTICE`：商标声明、第三方组件声明；
- `README.md` 中的非官方声明、隐私说明和免责声明。

如果权属需要调整，只改 `LICENSE` 第一行和 `pyproject.toml` 的 `authors` 即可。

---

## 二、本仓库已经准备好的东西

```text
LICENSE                          MIT 许可证
NOTICE                           商标与第三方组件声明
README.md                        中文主页（含徽章、用法、FAQ、免责声明）
README.en.md                     英文简介
CHANGELOG.md                     变更记录
CONTRIBUTING.md                  贡献指南
CODE_OF_CONDUCT.md               行为准则
SECURITY.md                      安全政策
docs/usage.md                    完整使用手册
docs/design.md                   架构与实现说明
docs/PUBLISHING.md               本文
.github/workflows/ci.yml         三平台 CI
.github/workflows/release.yml    打标签自动构建 exe 并发布
.github/ISSUE_TEMPLATE/*.yml     Issue 模板
.github/pull_request_template.md PR 模板
scripts/build_exe.py             PyInstaller 构建脚本
tests/                           74 个单元测试
```

## 三、安装并配置 Git

### 3.1 安装

- Windows：下载 [Git for Windows](https://git-scm.com/download/win)，
  一路默认安装即可；
- macOS：`xcode-select --install` 或 `brew install git`；
- Linux：`sudo apt install git`。

验证：

```bash
git --version
```

### 3.2 配置身份

名字和邮箱会写进每一次提交，请使用你希望公开的信息：

```bash
git config --global user.name "你的名字"
git config --global user.email "你的GitHub邮箱"
```

如果只想为本项目单独设置，去掉 `--global`，在项目目录中执行。

### 3.3 注册 GitHub

1. 打开 https://github.com 注册账号；
2. 在 Settings → Emails 中确认邮箱已验证；
3. 建议开启两步验证（2FA），否则 GitHub 会限制部分操作。

---

## 四、创建远程仓库并推送

### 4.1 在 GitHub 上新建仓库

1. 点击右上角 `+` → **New repository**；
2. Repository name 填 `goodnotes-attachment-extractor`；
3. Description 填一句话：
   `从 GoodNotes 导出的 .goodnotes 文件中提取音频、图片和 PDF 附件。`
4. 选择 **Public**；
5. **不要**勾选 "Add a README file"、"Add .gitignore"、"Choose a license"，
   因为本地已经有了；
6. 点击 **Create repository**。

### 4.2 推送本地代码

本目录已经完成 `git init` 和首次提交。在项目目录中执行：

```bash
# 查看当前状态，确认没有敏感文件
git status

# 关联远程仓库（把用户名换成你的）
git remote add origin https://github.com/ou0826/goodnotes-attachment-extractor.git

# 如果首次提交的作者信息需要修改
git config user.name "你的名字"
git config user.email "你的GitHub邮箱"
git commit --amend --reset-author --no-edit

# 推送
git branch -M main
git push -u origin main
```

推送时会要求登录。推荐使用 **Personal Access Token** 或 **GitHub Desktop**：

- 命令行：GitHub → Settings → Developer settings → Personal access tokens →
  Tokens (classic) → Generate new token，勾选 `repo` 权限，把 token 当作密码输入；
- 图形化：安装 [GitHub Desktop](https://desktop.github.com/)，登录后
  **File → Add local repository**，选择本目录，点击 **Publish repository**。

> 如果提示 `remote origin already exists`，先执行
> `git remote set-url origin <新地址>`。

### 4.3 仓库设置

推送成功后，在仓库页面点击右上角 **About** 旁的齿轮：

- Description：同上；
- Website：可留空；
- Topics：`goodnotes`、`note-taking`、`attachment`、`extractor`、`python`、
  `tkinter`、`protobuf`、`windows`；
- 勾选 **Issues**、**Discussions**（可选）。

然后在 Settings 中：

- 确认默认分支是 `main`；
- Branches → 添加 `main` 分支保护规则（Require a pull request before merging、
  Require status checks to pass），可以防止自己误推；
- Actions → General → 确认允许运行工作流。

---

## 五、发布第一个版本（Release）

### 5.1 推荐：打标签自动构建

仓库里的 `.github/workflows/release.yml` 会在推送 `v*` 标签时自动：

1. 在 Windows 上安装依赖；
2. 用 PyInstaller 构建单文件 exe；
3. 创建 GitHub Release 并上传 exe。

操作：

```bash
git tag -a v1.0.1 -m "v1.0.1 首个开源版本"
git push origin v1.0.1
```

然后打开仓库的 **Actions** 页面查看进度。完成后在 **Releases** 页面就能看到
`GoodNotes-Attachment-Extractor-v1.0.1-win64.exe`。

### 5.2 备用：手动构建并上传

如果 CI 构建失败：

```bash
python -m pip install -e ".[dev]"
python scripts/build_exe.py
```

产物在 `dist/` 下：

- `GoodNotes-Attachment-Extractor.exe`：命令行版
- `GoodNotes-Attachment-Extractor-GUI.exe`：图形界面版

在 GitHub 仓库页面：

1. 右侧 **Releases** → **Draft a new release**；
2. Choose a tag → 输入 `v1.0.1` → Create new tag；
3. 标题填 `v1.0.1`，说明可以从 `CHANGELOG.md` 复制；
4. 把两个 exe 拖进附件区域，建议重命名为
   `...-win64.exe` 和 `...-win64-GUI.exe`；
5. 点击 **Publish release**。

> Release 附件不要提交进 Git 仓库。仓库只保存源码，二进制走 Releases。

---

## 六、发布后的社区运营

### 6.1 标签建议

在 Issues → Labels 中创建：

- `bug`（红色）、`enhancement`（蓝色）、`documentation`（灰色）、
  `good first issue`（绿色）、`help wanted`（黄色）、`question`（紫色）。

### 6.2 回复原则

- 24–72 小时内给个初步回应，哪怕只是"我看到了，周末看"；
- 要复现信息时，明确要求**脱敏**，不要索要原始笔记文件；
- 对不打算实现的需求，说明原因并关闭，比沉默更好。

### 6.3 发版流程

1. 修改代码并更新 `CHANGELOG.md`（把 `Unreleased` 内容移到新版本号下）；
2. 提交 PR 并合并；
3. 打标签 `v1.1.0` 并推送；
4. 等待 Actions 自动发布；
5. 在 Discussions 或 Release 说明中写清升级注意事项。

版本号遵循语义化版本：不兼容变更升主版本，新功能升次版本，修 Bug 升修订号。

---

## 七、常见问题

**Q：`git push` 报 `Support for password authentication was removed`**
A：GitHub 不再接受账号密码。请使用 Personal Access Token（当密码用）或 SSH Key，
或者改用 GitHub Desktop / VS Code 的登录功能。

**Q：提交里出现了中文文件名乱码**
A：执行 `git config --global core.quotepath false`，让 Git 正常显示中文路径。

**Q：不小心提交了 `.goodnotes` 或个人信息**
A：立刻停止推送。如果还没推送，`git rm --cached <文件>` 后重新提交；如果已经推送，
需要重写历史（`git filter-repo`）并强制推送，同时把文件视为已泄露，必要时更换相关
密钥/邮箱。**不要**只在新提交里删除文件，历史中仍然可见。

**Q：README 里的徽章不显示**
A：徽章地址中的 `ou0826` 还没替换，或者 CI 还没运行过。

**Q：CI 在 Ubuntu 上失败，提示没有 tkinter**
A：CI 只运行测试，不启动 GUI。如果以后给 GUI 加测试，需要在 Ubuntu 上安装
`python3-tk`。当前测试不会导入 `gui.py` 以外的 tkinter 依赖。

**Q：Actions 不能创建 Release**
A：检查 Settings → Actions → General → Workflow permissions，选择
"Read and write permissions"。

---

## 八、法律文本补充说明

本仓库已经包含常用的开源法律文件，一般足够。以下情况建议额外处理：

| 情况 | 建议 |
| --- | --- |
| 学校/单位是著作权人 | 取得书面开源同意，LICENSE 版权人改为单位 |
| 项目使用了他人代码 | 在 NOTICE 中列出原项目和许可证，并保留其版权声明 |
| 想提供商业版/付费支持 | MIT 允许，但需在 README 中说明两者关系 |
| 收到侵权投诉 | 先下架相关内容，保留沟通记录，必要时咨询律师 |
| 想注册项目名商标 | 先做商标检索，注意不要与 GoodNotes 混淆 |

再次提醒：本文不是法律意见。涉及权属、职务成果、出口管制或商业合作时，请咨询
专业人士或学校相关部门。
