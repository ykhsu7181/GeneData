# GeneData afd758c 生产发布包校验报告

> 日期：2026-10-14  
> 发布代码：`afd758cfa381c301190b78c6dbba29fb9b31f950`  
> 结论：开发机正式候选包通过独立校验；生产上传、备份、切换和业务验收仍待执行。

## 1. 交付物

| 交付物 | 路径 |
| --- | --- |
| 发布目录 | `D:\gene_manage_system\production_release_afd758c\GeneData_afd758c_20261014` |
| 正式 ZIP | `D:\gene_manage_system\production_release_afd758c\GeneData_afd758c_20261014.zip` |
| 外层校验文件 | `D:\gene_manage_system\production_release_afd758c\GeneData_afd758c_20261014.zip.sha256` |
| 包内校验清单 | `GeneData_afd758c_20261014/SHA256SUMS` |
| 部署执行单 | `docs/GeneData_afd758c_生产环境部署执行单_20261014.md` |

正式 ZIP 的 SHA-256：

```text
3eea9b5226edaf705b03b3244e37fd44b3cefcd79f35c76f30ab2f009a6cf34c
```

## 2. 发布身份与范围

- 源提交：`afd758cfa381c301190b78c6dbba29fb9b31f950`。
- 源分支：`feat/homepage-portal-redesign`。
- 远端分支在打包前已 fetch 复核，ahead/behind 为 `0/0`，远端引用指向完整源提交。
- 构建来源：仓库外的 detached worktree `D:\gene_manage_system\release_worktrees\GeneData_afd758c_20261014`。
- JBrowse Web：`4.3.0`。
- 包含：Django 后端、干净 worktree 生成的前端 `dist`、JBrowse Web 4.3.0、`afd758c` 对应响应式插件、Nginx 示例和 JBrowse 构建脚本。
- 排除：密钥、数据库、`manual_files`、`derived_data`、日志、虚拟环境、`node_modules`、`.git`、浏览器证据、隔离数据及 JBrowse 上游 `test_data`。

生产机当前运行提交必须在部署前现场记录。发布元数据中的 `reported_production_baseline=06a4216_verify_on_host` 仅是既有记录，不替代生产进程和文件核对。

## 3. 干净 worktree 回归

| 检查 | 结果 |
| --- | --- |
| `python manage.py check` | PASS，无系统检查问题 |
| `python manage.py makemigrations --check --dry-run files` | PASS，`No changes detected` |
| `python manage.py test files --settings=filemanager.settings_sqlite_test --noinput` | PASS，397 项通过，2 项跳过 |
| `npm test` | PASS，176/176 |
| `npm run lint` | PASS |
| `npm run build` | PASS |

前端构建仅出现既有 asset/entrypoint 体积警告。`npm ci` 报告 68 项依赖审计问题，并提示 Node 25 超出一个旧依赖声明的支持范围；本次锁文件安装、测试、Lint 和构建均成功，且 `node_modules` 不进入生产包。依赖升级需单独评估，禁止在发布准备中运行 `npm audit fix --force`。

## 4. 独立包校验

Windows 使用新的解压目录 `D:\gene_manage_system\release_verification\GeneData_afd758c_20261014_candidate3` 验证，结果如下：

| 检查 | 结果 |
| --- | --- |
| 外层 SHA-256 | PASS |
| ZIP 条目数 | 1159 |
| 包内逐文件 SHA-256 | PASS，1158/1158 |
| ZIP 反斜杠路径 | 0 |
| 禁入目录 | 0 |
| 关键路径 | PASS，8/8 |
| `RELEASE_INFO.txt` 源提交 | PASS |
| JBrowse 版本 | PASS，4.3.0 |
| 发布插件与 `afd758c` 源插件哈希 | PASS |

响应式插件 SHA-256：

```text
50f2abd3336ace2d7f68d9c7e1b7aca9430ae24e83f1d88cafcda666fb5a1421
```

Ubuntu/WSL 另行执行外层 `sha256sum -c`、解压、包内 `sha256sum -c SHA256SUMS` 和版本核对，结果均为 PASS。

## 5. 拒绝候选

下列失败候选已保留用于审计，禁止上传或部署：

- `DO_NOT_DEPLOY_backslash_paths_GeneData_afd758c_20261014.zip`：ZIP 条目包含反斜杠路径；
- `DO_NOT_DEPLOY_empty_candidate_2_GeneData_afd758c_20261014.zip`：归档工具初始化失败后留下的空文件。

生产上传时只能选择不带 `DO_NOT_DEPLOY` 前缀的正式 ZIP 及其同名 `.sha256`。

## 6. 仍待生产完成

- 上传后的外层和包内 SHA-256 复核；
- 当前进程 PID、cwd、Python、settings、环境变量和实际生产代码身份核对；
- 数据库、活动后端、前端、Nginx 和当前 JBrowse Web 备份；
- 新后端生产 settings 检查及 migration plan；
- 代码、前端和 JBrowse 响应式插件切换；
- Assembly 1400、93 的映射 dry-run、逐个 apply 和全链路验收；
- 状态、定位、配置、四类 Range 206、正确轨道与目标特征、返回上下文和旧功能回归；
- 回滚材料路径、校验值和最终验收证据归档。

上述项目只有保存实际生产输出后才能标记为 PASS。
