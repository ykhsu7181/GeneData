# GeneData：从注释结果一键定位内置 JBrowse 阶段 E-0 生产发布前收口记录

> 日期：2026-10-14
> 当前状态：**代码边界、开发回归、候选文件清单和生产门禁已收口；实施提交 `0cb0fb4` 已推送，尚未生成可部署发布包。**
> 环境边界：本阶段没有连接生产环境，没有执行生产 dry-run 或 apply。

## 1. 基线与发布原则

- 当前分支：`feat/homepage-portal-redesign`；工作区基线提交：`fc3c58251189ca025a2030a72dab7fe4789b2dda`。
- 一键定位实施提交：`0cb0fb4f4d268abb9b9cbb50bb9197907c5a786f`，已推送至 `origin/feat/homepage-portal-redesign`。
- 本地跟踪信息显示相对 `origin/feat/homepage-portal-redesign` 为 ahead 5、behind 0；本阶段未执行远端 fetch，因此该结论只代表本地远端引用。
- 当前工作区混有历史生产文档、实验记录、隔离数据和其他任务文件，禁止从当前目录整体归档。
- 正式发布包必须来自“一键定位变更已独立提交”的干净 detached worktree，并重新计算包内清单和外层 SHA-256；本阶段的源文件哈希只是提交前快照，标记为 `DO NOT DEPLOY`。

## 2. 候选代码白名单

提交前快照共 27 个文件，完整 SHA-256 见：

```text
release_manifests/jbrowse_oneclick_20261014/SOURCE_SHA256.txt
```

组成如下：

- Django 运行时代码 11 个：定位 API、状态/配置门禁、特征索引版本、refName 映射服务与命令、文件角色、URL 和查询缓存版本；
- Django 测试 6 个：状态、配置、资产隔离、定位 API、回填命令、refName 服务；
- Vue 运行时代码 6 个：注释表入口、浏览器页、两个安全导航工具和中英文文案；
- Vue 测试 3 个；
- 开发启动脚本 1 个，仅把 Vue 冷启动等待上限改为 180 秒。

实施方案与阶段 A–E0 记录可随源码提交，但不属于生产运行时文件。

### 2.1 明确排除

以下内容不进入本功能提交或生产发布包：

- `.artifacts/` 浏览器截图、临时脚本及其他历史 QA 产物；
- `manual_files_quarantine/`；
- `django2/metadata/production_full_manifest_20260924/`；
- 与本功能无关的根目录方案、历史生产部署指南、Word 实验记录和插图；
- `vue_project/dist/`、`node_modules/`、数据库、缓存、日志、密钥和任何生产数据文件。

## 3. 最终开发回归

本次 E-0 在当前候选源码上重新执行：

```text
python manage.py check
System check identified no issues

python manage.py makemigrations --check --dry-run files
No changes detected in app 'files'

python manage.py test files --settings=filemanager.settings_sqlite_test --noinput
Ran 397 tests: OK (skipped=2)

npm test
173 passed, 0 failed

npm run lint
退出码 0

npm run build
退出码 0
```

构建仍只有既有的 asset/entrypoint 体积警告。`git diff --check` 通过，仅显示 Windows 工作区的 LF/CRLF 提示。运行时代码扫描未发现写死的用户目录、仓库绝对路径、私钥或凭据；开发脚本中的 `/home/$wslUser/genedata-jbrowse-runtime` 是按当前 WSL 用户动态生成的开发路径，两个 `password` 命中是登录界面翻译键。

## 4. 形成正式发布包前的门禁

1. 已只选择第 2 节白名单及本功能 A–E0 文档创建独立实施提交 `0cb0fb4`，未使用 `git add .`。
2. 推送后已 fetch 复核，本地与 `origin/feat/homepage-portal-redesign` 的分歧为 `0/0`。
3. 从最终发布提交创建干净 detached worktree，重新执行第 3 节回归。
4. 从仓库根目录归档，包内路径统一使用 `/`，不得包含 `.git`、运行数据、密钥、日志、缓存、隔离文件或本地浏览器证据。
5. 独立解压发布包，验证所有内部 SHA-256、关键路径和外层 ZIP SHA-256；任何不一致的候选包标记为 `DO_NOT_DEPLOY`。

正式 ZIP 尚未生成；提交前 SHA 清单仍只用于证明收口时的文件边界，不能替代从最终提交生成的发布清单。

## 5. 生产只读门禁

部署代码前保存当前提交、进程 PID/cwd、环境配置、数据库备份校验值，以及 Assembly 1400/93 当前 FASTA、FAI、Annotation、JBrowse GFF3/TBI 和 FileRelation 清单。确认生产 Python、Django settings、数据库和物理文件根目录后，先运行：

```bash
cd <production-project>/django2
source <production-venv>/bin/activate

python manage.py check
python manage.py makemigrations --check --dry-run files

python manage.py backfill_jbrowse_refname_aliases --assembly-id 1400 --dry-run
python manage.py backfill_jbrowse_refname_aliases --assembly-id 93 --dry-run
```

两个试点必须分别满足：

- `status=ready_for_build`、`write_performed=false`；
- `ambiguous_alias_count=0`；
- `reference_count/alias_count` 与阶段 A 核对结果相符；
- `planned_path` 位于受控的 JBrowse 派生目录；
- 选中的 primary FASTA/FAI 唯一、可读且与当前生产索引一致。

任一条件不满足即停止，不执行 apply。dry-run 输出、命令退出码、执行时间和文件清单须作为生产证据保留。

## 6. 后续写入、验证和回滚边界

生产 apply 不属于 E-0。进入下一阶段后应先处理 Assembly 1400，完整验收通过后再处理 Assembly 93：

```bash
python manage.py backfill_jbrowse_refname_aliases --assembly-id 1400 --apply
python manage.py backfill_jbrowse_refname_aliases --assembly-id 93 --apply
```

每个试点 apply 后分别验证：唯一 primary `jbrowse_refname_aliases` 关系、映射 JSON 指纹、`jbrowse-status` 的 `location_ready=true`、真实 `feature_id` 定位、配置一致性、四类资产 206 Range、正确轨道/目标特征、返回上下文和物理路径不泄露。IR64 应使用阶段 A 固定的 `Chr01` 特征，W2275 应解析到 `GWHESLA00000001`。

apply 前必须同时备份数据库和目标映射路径。若验收失败，先关闭一键定位入口并回退代码；映射写入的回滚使用已校验的数据库备份和映射目录备份，不通过临时 SQL、直接删除 `DataFile/FileRelation` 或删除整个派生目录处理。

## 7. 当前结论

E-0 的技术收口和独立实施提交已经完成。剩余门禁是以最终发布提交创建干净 detached worktree，重新执行回归并生成正式发布包、内部清单、外层 SHA-256 和独立校验报告。生产环境仍为待验证状态。
