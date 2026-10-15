# GeneData JBrowse 2 阶段一生产环境只读检查记录

## 1. 记录信息

- 检查日期：2026-09-24
- 后续补充检查日期：2026-09-28
- 检查阶段：JBrowse 2 实施阶段一——生产环境只读检查
- 生产主机用户：`rdcheng`
- GeneData 生产代码目录：`/home/labuser/rdcheng/gd/django2`
- 生产原始文件目录：`/home/labuser/rdcheng/gd/manual_files`
- 生产 Django 端口：`2025`
- 检查方式：Shell 命令、Django ORM 只读查询、HTTP 只读请求
- 原始数据修改：未执行
- 数据库写入：未执行
- 服务重启：未执行
- Nginx 修改或 reload：未执行

相关方案：[`GeneData_JBrowse2内置基因组浏览器实施方案.md`](./GeneData_JBrowse2内置基因组浏览器实施方案.md)

## 2. 检查边界

本次只读检查用于确认：

1. 生产目录和原始文件是否存在且可读；
2. FASTA、GFF及Manifest数量和文件实体是否一致；
3. IR64参考基因组和注释是否适合作为JBrowse原型；
4. 生产Django进程使用的解释器和配置；
5. 生产数据库中的IR64 Assembly、Annotation和DataFile关系；
6. Node.js、JBrowse CLI、samtools、bgzip和tabix是否可用；
7. 磁盘空间是否满足后续衍生索引构建；
8. 当前公共API是否正确隐藏历史占位Assembly；
9. 当前Nginx是否具备后续Range文件服务的配置基础。

本次未执行：

- `build_fasta_indexes`；
- `build_jbrowse_indexes`；
- `bind_manual_files --apply`；
- `cleanup_placeholder_hierarchy --apply`；
- `samtools faidx`；
- `bgzip`压缩；
- `tabix`建索引；
- 软件安装或升级；
- 数据库迁移；
- 任何生产服务停止、重启或配置重载。

## 3. 总体结论

阶段一的数据与文件检查总体通过：

- 607个参考基因组FASTA全部存在；
- 517个Annotation源文件全部存在；
- Manifest中2240条映射文件均可读取，无缺失、空文件或越界路径；
- IR64 FASTA与GFF均使用12个相同seqid；
- IR64 GFF共有715004条特征，未发现非九列记录；
- IR64 attributes符合GFF3的`key=value`、`ID`和`Parent`形式；
- 517个注释文件快速分类均属于已声明GFF3或可能缺少声明的GFF3，未发现GTF或未知格式；
- samtools、bgzip和tabix可用；
- 当前可用磁盘空间约5.6TB，足以支持首批和预计的全量JBrowse衍生索引。

后续只读检查已经确认：

1. 历史占位Assembly ID 166返回200的原因是生产发布目录缺少`files/services/assembly_visibility.py`，且当前`assembly_api_views.py`仍直接使用`Assembly.objects`；
2. 生产目录不是Git工作区，属于发布包部署，后续必须通过完整发布包补齐代码，不能现场复制单个文件；
3. Nginx配置语法检查通过，`/gb/`正确指向GeneData前端构建目录，`/gd/api/`正确代理到2025；
4. 当前Nginx尚无JBrowse静态路径、受保护内部文件location和`X-Accel-Redirect`文件服务，这些属于后续实施内容。

因此本阶段最终状态为：

```text
PASS_WITH_FOLLOW_UP
```

阶段一只读检查正式结束，可以在开发环境进入阶段二。生产索引构建和JBrowse入口开放仍需等待完整代码发布、隔离Node/JBrowse环境和受保护文件服务完成。

## 4. 生产目录与权限检查

### 4.1 检查结果

```text
whoami
rdcheng

pwd
/home/labuser/rdcheng/gd/django2

readlink -f "$MANUAL_ROOT"
/home/labuser/rdcheng/gd/manual_files

manual_files directory: PASS
manual_files readable: PASS
```

结论：

- 生产原始文件目录存在；
- 当前用户可以读取该目录；
- IR64 FASTA和GFF路径可以解析并读取。

### 4.2 权限警告

检查中看到至少部分生产源文件对当前用户可写。虽然本次没有执行写操作，但操作系统层面未完全强制`manual_files`只读。

当前处理：

- 记录为`WARN_SOURCE_WRITABLE`；
- 本阶段不执行`chmod`或属主修改；
- 后续索引服务必须仅以只读方式打开源文件；
- 所有产物必须写入独立`derived_data`目录；
- 是否调整生产权限需另行完成依赖审计后由管理员决定。

## 5. 运行环境检查

### 5.1 Python与Django

生产GeneData进程PID检查结果：

```text
command:
python manage.py runserver 0.0.0.0:2025 --noreload \
  --settings=filemanager.settings_production

python executable:
/home/Software/anaconda3/envs/django2_env/bin/python3.9

CONDA_PREFIX:
/home/Software/anaconda3/envs/django2_env

DJANGO_SETTINGS_MODULE:
filemanager.settings_production

PYTHONPATH:
/home/labuser/rdcheng/gd/django2

Python:
3.9

Django:
3.2.9
```

结论：生产Django解释器和运行环境已经确认。最初在Conda `base`环境执行`manage.py`时出现`No module named 'django'`，属于环境选择错误，不是生产应用缺少Django。

直接使用生产解释器但未继承进程环境时，曾出现：

```text
RuntimeError: Required production environment variable is missing: DJANGO_SECRET_KEY
```

原因是新Shell没有继承生产进程的环境变量。后续只读ORM查询通过临时子Shell继承PID环境完成，未显示或记录Secret值。

### 5.2 Node.js与JBrowse CLI

```text
Node.js: v6.17.1
npm: 3.10.10
JBrowse command: /usr/bin/jbrowse
```

执行`jbrowse --version`失败，关键信息为：

```text
Node version must be >=8.0.0 to use this CLI
Current node version: 6.17.1
SyntaxError: Unexpected identifier
```

`vue_env`仍然解析到系统Node.js 6.17.1和`/usr/bin/jbrowse`，不能作为JBrowse 2运行环境。

结论：

- 当前JBrowse CLI不可用；
- 不应替换系统Node.js或修改现有`vue_env`；
- 下一阶段需要创建隔离的Node.js 18/20环境并安装固定版本JBrowse 2 CLI；
- 该问题不影响本次文件只读检查，但阻止JBrowse索引命令直接执行。

### 5.3 生物信息工具

```text
samtools 1.11
htslib 1.11
bgzip (htslib) 1.11
tabix (htslib) 1.11
```

结论：生成FAI、bgzip文件和Tabix索引所需的基础工具存在。当前只检查版本，未生成任何索引。

### 5.4 Nginx

```text
nginx version: nginx/1.23.1
```

普通用户执行`sudo nginx -T`时返回：

```text
rdcheng is not in the sudoers file
```

后续由root用户完成只读检查。生效配置文件为：

```text
/home/Software/nginx/conf/nginx.conf
```

语法检查结果：

```text
nginx: the configuration file /home/Software/nginx/conf/nginx.conf syntax is ok
nginx: configuration file /home/Software/nginx/conf/nginx.conf test is successful
```

GeneData前端配置：

```nginx
location /gb/ {
    alias /home/labuser/rdcheng/gd/dist/;
    try_files $uri $uri/ /gb/index.html;
    index index.html;
    client_max_body_size 10G;
}
```

GeneData API配置：

```nginx
location /api/ {
    rewrite ^/api/(.*) /gd/api/$1 break;
    proxy_pass http://localhost:2025/;
}

location /gd/api/ {
    client_max_body_size 10G;
    proxy_pass http://localhost:2025;
    proxy_connect_timeout 300s;
    proxy_send_timeout 300s;
    proxy_read_timeout 300s;
}
```

检查结论：

- Nginx二进制存在；
- Nginx配置语法检查通过；
- `/gb/`使用`alias /home/labuser/rdcheng/gd/dist/`，并正确配置Vue Router回退；
- `/api/`会重写到`/gd/api/`并转发到2025；
- `/gd/api/`直接代理到GeneData的2025端口；
- 未发现`/jbrowse2/`静态应用location；
- 未发现面向`manual_files`或`derived_data`的受保护`internal` location；
- 未发现现有`X-Accel-Redirect`文件服务；
- 在本次筛选输出中未发现相关gzip配置，后续JBrowse压缩索引location仍应显式设置`gzip off`；
- 当前配置不能直接提供JBrowse所需的安全Range文件读取，需要在后端浏览器文件接口完成后新增配置并验证206响应；
- 本次未修改或reload Nginx。

本项状态：

```text
PASS_WITH_FOLLOW_UP
```

## 6. 磁盘与inode检查

```text
Filesystem: /dev/mapper/centos-home
Size:       107T
Used:       102T
Available:  5.6T
Use%:       95%

Inodes:     2296066752
IUsed:      15270970
IFree:      2280795782
IUse%:      1%
```

结论：

- inode充足；
- 绝对剩余空间约5.6TB，明显大于当前约36.9GiB注释源文件总量；
- 文件系统利用率已经达到95%，属于高水位，需要持续监控；
- 后续不复制约224.9GiB的FASTA，只生成较小的FAI；
- GFF标准化、排序、压缩和临时文件必须写入`derived_data`；
- 建议索引任务串行或低并发执行，并预留至少100GB安全余量。

当前`derived_data`目录不存在。本阶段未创建目录，属于预期结果。

## 7. Manifest与文件实体验收

### 7.1 Manifest表头

生产Manifest可读取，但表头字段包含额外双引号：

```text
"file_path"
"file_role"
"accession"
"assembly_code"
"annotation_code"
"sample_code"
"dataset_code"
"md5"
```

最初检查脚本因直接读取`file_path`出现：

```text
KeyError: 'file_path'
```

修正方式：使用`utf-8-sig`读取，并对字段名执行去BOM、去空白和去双引号处理。该问题属于Manifest格式兼容问题，不是文件数据损坏。

### 7.2 角色数量

检查结果：

| file_role | Manifest数量 | 实体存在数量 | 结果 |
|---|---:|---:|---|
| `genome` | 607 | 607 | PASS |
| `annotation` | 517 | 517 | PASS |
| `coreBlocks` | 152 | 152 | PASS |
| `rRNA` | 152 | 152 | PASS |
| `tRNA` | 152 | 152 | PASS |
| `TEs` | 151 | 151 | PASS |
| `centromere` | 151 | 151 | PASS |
| `miRNA` | 151 | 151 | PASS |
| `codon` | 111 | 111 | PASS |
| `transcriptome.all` | 2 | 2 | PASS |
| `transcriptome.leaf` | 20 | 20 | PASS |
| `transcriptome.panicles` | 10 | 10 | PASS |
| `transcriptome.root` | 37 | 37 | PASS |
| `transcriptome.shoot` | 26 | 26 | PASS |
| `transcriptome.stem` | 1 | 1 | PASS |

```text
problem_count = 0
```

确认没有：

- Manifest引用文件缺失；
- 文件不可读；
- 文件大小为零；
- 文件路径超出`manual_files`根目录。

### 7.3 文件规模

| 类型 | 总字节数 | 约合大小 |
|---|---:|---:|
| Genome FASTA | 241507351715 | 224.9GiB |
| Annotation GFF | 39597214908 | 36.9GiB |
| 最大Annotation | 196608107 | 187.5MiB |

最大Annotation文件：

```text
/home/labuser/rdcheng/gd/manual_files/annotation.PPR1.gff
```

## 8. IR64数据检查

### 8.1 文件

```text
/home/labuser/rdcheng/gd/manual_files/genome.IR64.fasta
/home/labuser/rdcheng/gd/manual_files/annotation.IR64.gff
```

### 8.2 FASTA与GFF结构

```text
fasta_sequence_count = 12
gff_feature_count = 715004
gff_seqid_count = 12
gff_version = None
detected_format = likely_gff3_without_header
malformed_count = 0
malformed_samples = []
gff_seqids_missing_from_fasta = []
unannotated_fasta_seqids = []
```

结论：

- FASTA与GFF均使用12个相同seqid；
- GFF没有无法对应到FASTA的序列；
- FASTA不存在完全未注释的序列；
- 没有非九列记录；
- 文件缺少`##gff-version 3`声明。

### 8.3 Attributes检查

抽样记录符合以下结构：

```text
gene  ID=gene:...
mRNA  ID=transcript:...;Parent=gene:...
exon  Parent=transcript:...
CDS   ID=CDS:...;Parent=transcript:...
```

完整统计：

```text
total=715004
with_ID=326491
with_Parent=678079
gtf_style=0
attributes_without_equal=0
```

结论：IR64属于有效GFF3 attributes语法但缺少版本声明。后续索引程序应在衍生输出中补充：

```text
##gff-version 3
```

不得修改原始`annotation.IR64.gff`。

## 9. 全量GFF快速格式分类

对517个Annotation文件前500行进行只读快速分类：

```text
declared_gff3                 220
likely_gff3_without_header    297
likely_gtf                      0
unknown                         0
```

结论：

- 所有517个源文件均具有GFF3处理基础；
- 220个文件明确声明GFF3；
- 297个文件可能是缺少版本声明的GFF3；
- 未发现GTF风格文件；
- 未发现无法识别格式。

限制：本检查只读取每个文件前500行。297个未声明文件仍需在实际索引构建的dry-run阶段执行全文件九列、attributes、父子关系和seqid检查，不能仅凭快速分类直接认定全文件完全有效。

## 10. IR64数据库关系检查

数据库中IR64当前存在两个Assembly：

### 10.1 历史占位Assembly

```text
Assembly ID:      166
assembly_code:    None
name:             default
is_default:       False
primary genome:   DataFile 1143, genome.IR64.fasta, role=genome
Annotation count: 0
```

### 10.2 真实Assembly

```text
Assembly ID:      1400
assembly_code:    ASM_IR64
name:             IR64 genome assembly
is_default:       True
primary genome:   DataFile 1143, genome.IR64.fasta, role=genome
Annotation count: 1

Annotation ID:    697
annotation_code:  ANN_IR64
name:             IR64 annotation
is_default:       True
source DataFile:  331
source file:      annotation.IR64.gff
source primary:   True
```

JBrowse的IR64原型必须使用：

```text
Assembly ID 1400
Annotation ID 697
FASTA DataFile ID 1143
GFF DataFile ID 331
```

不得为Assembly ID 166生成JBrowse配置。

## 11. 历史占位Assembly异常

本地当前代码包含Assembly可见性过滤规则，严格占位Assembly在存在真实替代对象时应从详情和公共列表隐藏。

生产HTTP检查结果：

```text
GET /gd/api/files/assemblies/166/summary/  -> HTTP 200
GET /gd/api/files/assemblies/1400/summary/ -> HTTP 200
```

预期结果应为：

```text
Assembly 166 -> HTTP 404
Assembly 1400 -> HTTP 200
```

后续生产磁盘代码检查结果：

```text
files/assembly_api_views.py:41
queryset = Assembly.objects.select_related("accession", "accession__species").all()

files/services/assembly_visibility.py
MISSING

production directory is not a git worktree

SHA-256 files/assembly_api_views.py
fef56a49e5234a02fdb2a26d9ecda95804013278367077e2fe759a6bb6b180d3
```

根因已经确认：生产发布目录缺少Assembly可见性服务，当前Assembly接口仍使用未过滤的`Assembly.objects`，因此历史占位Assembly ID 166返回HTTP 200。该问题属于生产发布包代码版本不完整或偏旧，不是数据库查询异常。

由于Assembly 166仍关联DataFile 1143，现有保守清理逻辑会将其识别为`assembly_has_file_relations`并阻止直接删除。

当前要求：

- 不运行`cleanup_placeholder_hierarchy --apply`；
- 不手工删除Assembly 166；
- 不解除FileRelation；
- 不重启PID 35429；
- 不在生产目录临时复制单个`assembly_visibility.py`或手工修改接口文件；
- 下一次使用完整发布包同时更新可见性服务、Assembly接口和相关测试；
- 完整发布后按计划重启2025服务，并重新验证166返回404、1400返回200；
- JBrowse构建和配置接口必须使用`visible_assembly_queryset()`；
- 修复部署并完成回归验证前不开放生产JBrowse入口。

本项状态：

```text
ROOT_CAUSE_CONFIRMED_PENDING_RELEASE
```

## 12. 阶段一验收状态

| 检查项 | 状态 | 说明 |
|---|---|---|
| 生产目录存在且可读 | PASS | `/home/labuser/rdcheng/gd/manual_files` |
| 生产源文件保持未修改 | PASS | 本次未执行写操作 |
| Django运行环境 | PASS | Python 3.9、Django 3.2.9、`django2_env` |
| samtools/bgzip/tabix | PASS | htslib 1.11 |
| Node/JBrowse CLI | FOLLOW_UP | Node 6.17.1过旧，阶段二需建立隔离环境 |
| Manifest格式读取 | PASS_WITH_COMPATIBILITY | 需要清理带引号字段名 |
| Manifest文件实体 | PASS | 2240条映射，`problem_count=0` |
| 607个Genome FASTA | PASS | 全部存在且可读 |
| 517个Annotation | PASS | 全部存在且可读 |
| IR64 FASTA/GFF seqid | PASS | 12对12，完全匹配 |
| IR64 GFF九列结构 | PASS | 715004条，无异常行 |
| IR64 attributes | PASS | GFF3风格，无GTF和无等号属性 |
| 全量GFF快速分类 | PASS_WITH_FOLLOWUP | 297个无版本声明，构建时需全文件验证 |
| 磁盘容量 | PASS_WITH_WARNING | 可用5.6TB，但使用率95% |
| IR64真实Assembly | PASS | Assembly 1400、Annotation 697 |
| 历史占位Assembly | PASS_WITH_FOLLOW_UP | 根因已确认：生产发布包缺少可见性过滤，待完整发布修复 |
| Nginx配置语法 | PASS | `/home/Software/nginx/conf/nginx.conf`检查成功 |
| GeneData前端路由 | PASS | `/gb/`指向`/home/labuser/rdcheng/gd/dist/` |
| GeneData API路由 | PASS | `/gd/api/`代理到2025 |
| JBrowse静态路由 | FOLLOW_UP | 当前没有`/jbrowse2/`，待后续部署 |
| JBrowse受保护文件服务 | FOLLOW_UP | 当前没有`internal`/`X-Accel-Redirect`，待后续实现 |

## 13. 待办事项

### 13.1 已完成

1. 已确认生产磁盘代码缺少Assembly可见性服务。
2. 已确认Assembly 166返回200的根因。
3. 已保存当前`assembly_api_views.py`的SHA-256。
4. 已由root用户完成`nginx -t`和`nginx -T`只读检查。
5. 已确认`/gb/`静态目录和`/gd/api/`到2025的代理关系。
6. 已确认当前不存在JBrowse内部文件location和`X-Accel-Redirect`文件服务。

### 13.2 阶段二开始前完成

1. 创建独立Node.js 18/20环境；
2. 安装并固定JBrowse 2 CLI版本；
3. 规划`derived_data/jbrowse`目录、属主、权限和空间监控；
4. 在索引dry-run中对297个无版本声明GFF执行全文件验证；
5. 确认索引任务仅遍历可见真实Assembly和已批准FileRelation。
6. 在下一次完整代码部署中补齐Assembly可见性服务及相关调用，不进行单文件热补丁。
7. 后端浏览器文件接口完成后，新增`/jbrowse2/`、受保护`internal` location和`X-Accel-Redirect`配置。
8. 配置完成后使用Range请求验证`206 Partial Content`。

## 14. 当前决策

当前允许：

- 完善JBrowse索引和配置接口设计；
- 在开发环境实现代码和测试；
- 准备隔离Node/JBrowse运行环境方案；
- 正式进入阶段二开发。

当前不允许：

- 在生产环境生成FAI、GFF3.GZ或TBI；
- 创建或修改生产FileRelation；
- 删除占位Assembly 166；
- 修改`manual_files`；
- 重启生产Django服务；
- 修改或reload Nginx；
- 开放生产JBrowse入口。

阶段一最终结论：

```text
PASS_WITH_FOLLOW_UP
```

阶段一只读检查已关闭。后续事项已转入阶段二开发和生产发布前置条件，不再阻止本地代码实现，但继续阻止生产索引构建和入口开放。
