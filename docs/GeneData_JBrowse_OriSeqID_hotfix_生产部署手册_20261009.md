# GeneData JBrowse OriSeqID 热修复部署手册（2026-10-09）

## 范围与依据

当前生产运行 `b0a1ce8`，IR64 Assembly 1400 已完成索引、API Range 206 和浏览器联动验证。全量 dry-run 首批 20 个 Assembly 均为 `seqid_mismatch`。生产 FASTA 头使用 `GWHESH...` 主 ID，并在 `OriSeqID=` 中保存注释使用的 `chr1`、`W0103_054` 等名称；首批 20 个样本的缺失名称均能唯一映射。

本热修复只替换 Django 后端代码。预检现在通过 FASTA 的 `OriSeqID` 映射注释第一列，并检查名称歧义和坐标是否超出 FASTA 实际长度。构建时仅改写衍生 GFF3，`manual_files` 原始 FASTA/GFF 保持不变。前端、JBrowse Web、Nginx 配置和数据库模式均不变。

## 发布物与目录

发布包 `GeneData_JBrowse_alias_<commit>_20261009.zip` 和同名 `.sha256` 从本手册所在提交构建。将两文件上传到：

```text
/home/labuser/rdcheng/gd/uploads/
```

生产根目录为 `/home/labuser/rdcheng/gd`。以下命令由 `rdcheng` 执行；不要在 root 的 tmux 中启动 Django。部署前保存发布包的外层 SHA-256、内部 `SHA256SUMS` 结果、数据库备份、当前 `django2` 备份及服务 PID。

## 1. 验证并解包

```bash
cd /home/labuser/rdcheng/gd/uploads
sha256sum -c GeneData_JBrowse_alias_<commit>_20261009.zip.sha256
unzip -l GeneData_JBrowse_alias_<commit>_20261009.zip | tail -n 3
```

在 `/home/labuser/rdcheng/gd` 下创建一个新 staging 目录并解包；进入包根目录运行 `sha256sum -c SHA256SUMS`，必须全部为 `OK`。不得因权限错误而跳过校验。Windows 构建的 ZIP 可能携带不适合 Linux 的权限位；解包后按文件/目录类型恢复可读权限，再执行校验，不要更改文件内容。SHA256SUMS 使用 LF 换行。

## 2. 备份和部署前检查

维护窗口前，在生产服务仍运行时确认新目录中的 `django2/manage.py` 和 `files/services/jbrowse_index_service.py` 存在。将新 `django2` 复制到版本化目录 `/home/labuser/rdcheng/gd/releases/django2-<commit>`，比较副本和 staging 内容。使用运行中 Django 进程相同的 Python 与生产环境变量执行 `manage.py check --settings=filemanager.settings_production`，不得打印密钥或数据库密码。

切换前创建新时间戳的数据库备份，并用 `gzip -t`、SHA-256 验证；保存当前 `/home/labuser/rdcheng/gd/django2` 的压缩备份。已完成的旧备份不得覆盖。

## 3. 后端切换

先确认生产端口 2025 的进程由 `rdcheng` 在 `tmux` 会话 `django2` 中启动。进入该会话，按 `Ctrl+C` 停止旧进程，确认 PID 消失。在同一会话中执行下列等价操作，使用唯一时间戳，目标路径存在时停止：

```bash
export GD_ROOT=/home/labuser/rdcheng/gd
export CUTOVER_TS=$(date +%Y%m%d_%H%M%S)
mv "$GD_ROOT/django2" "$GD_ROOT/django2.pre_alias_$CUTOVER_TS"
cp -a "$GD_ROOT/releases/django2-<commit>" "$GD_ROOT/django2"
export PYTHONPATH="$GD_ROOT/django2"
cd "$GD_ROOT/django2"
python manage.py check --settings=filemanager.settings_production
python manage.py runserver 0.0.0.0:2025 --noreload --settings=filemanager.settings_production
```

`python` 必须是现有 `/home/Software/anaconda3/envs/django2_env/bin/python3.9`。保留原生产密钥、数据库变量和 JBrowse 数据目录变量。不要重新部署 `dist`、JBrowse Web 或 Nginx。若检查/启动失败，停止新进程，将新目录改名保留，再将 `django2.pre_alias_$CUTOVER_TS` 移回 `django2` 并用原会话环境重启。

## 4. 续跑与验收

首先确认 `/gd/api/files/assemblies/` 返回 200，IR64 的 `jbrowse-status` 仍为 `ready`，其四个资源的 Range 请求仍返回 206。

使用现有报告目录 `/home/labuser/rdcheng/gd/audit_reports/jbrowse`，先对首批 20 个失败记录执行 `--all --dry-run --batch-size 20 --resume --retry-failed`。新报告应显示 `failed_this_run=0`、`failed_checkpoint_count=0`、`successful_checkpoint_count=20`。若有 `coordinate_out_of_bounds`、`ambiguous_seqid_alias` 或其他失败，保留报告并调查源文件，不执行 apply。

随后以 `--all --dry-run --batch-size 20 --resume` 处理其余记录，直到 `remaining_count=0`，并逐批检查失败数。只有全部 dry-run 通过后，才以 `--all --apply --batch-size 10 --resume` 分批构建，每批审计 JSON/TSV 和 checkpoint。最终必须满足 `remaining_count=0` 与 `failed_checkpoint_count=0`，并抽样验证非 IR64 Assembly 的状态、配置、Range 206 和浏览器显示。命令退出码为 0 不代表每项成功；以报告计数为准。

## 5. 留存证据

保存发布包 SHA-256、内部校验结果、备份路径与校验、切换前后 PID、Django 检查输出、首批重试报告、全量 dry-run/apply 的 JSON/TSV/checkpoint、API 与浏览器验收记录。不要把生产密钥或数据库密码写入报告。
