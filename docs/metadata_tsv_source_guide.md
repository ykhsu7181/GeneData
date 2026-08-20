# Metadata TSV 内容获取与补充指南

本文档用于说明：补充 `metadata` 目录下各类 TSV 表时，数据应该从哪里来，以及是否需要根据 Accession 到 NCBI 逐个检索后人工录入。

## 核心结论

不建议一个 Accession 一个 Accession 手工去 NCBI 查询并录入。

更稳妥的方式是：

```text
批量抓取 NCBI 元数据 -> 生成候选 TSV -> 人工审核缺失和冲突项 -> dry-run 导入 -> 正式导入
```

也就是说，TSV 的补充应采用“机器批量生成 + 人工校对”的方式，而不是完全手工维护。

## 为什么不能只靠 Accession 去 NCBI 查

项目中的 Accession 多数是材料名或内部编号，例如：

```text
IR64
125619
GWX37
02428
C7
```

这些通常不是 NCBI 的正式 accession 编号。NCBI 中更常见的是：

```text
BioProject: PRJNAxxxxxx
SRA Project: SRPxxxxxx
Experiment: SRXxxxxxx
Run: SRRxxxxxx
BioSample: SAMNxxxxxx
Assembly: GCA_xxxxx / GCF_xxxxx
```

因此，不能简单地用 `125619`、`GWX37` 这类材料名直接去 NCBI 查询完整信息。更可靠的做法是先建立：

```text
材料 Accession -> SRP / SRX / SRR / BioSample / BioProject / Assembly
```

这层映射关系。

## 各类 TSV 的数据来源

### 1. accession_manifest.tsv

用途：补充 Accession 基础信息。

建议字段：

```text
accession
species_code
sub_population
country
region
longitude
latitude
description
alias
note
```

主要来源：

```text
species_code：课题组内部确认，水稻通常为 ORYZA_SATIVA
sub_population：已有数据库、论文、群体分类结果
country / region / 经纬度：NCBI BioSample 属性、论文补充表、课题组材料表
description：课题组材料说明、原始表备注
alias：材料别名、中文名、旧编号
```

注意：

```text
country / region 最好表示材料采集地，而不是提交单位所在地。
```

### 2. dataset_manifest.tsv

用途：补充 Project / Dataset，尤其是 NCBI BioProject 和 SRA 信息。

建议字段：

```text
accession
project_code
project_name
dataset_code
dataset_name
dataset_type
ncbi_bioproject
ncbi_sra
external_url
description
```

主要来源：

```text
NCBI BioProject
NCBI SRA
SRA Run Selector 导出的 CSV
已有外部链接，例如 SRP227298
课题组项目说明
```

如果已有链接：

```text
https://www.ncbi.nlm.nih.gov/sra/SRP227298
```

可以先整理为：

```text
dataset_code = SRP227298
ncbi_sra = SRP227298
external_url = https://www.ncbi.nlm.nih.gov/sra/SRP227298
```

BioProject 可以后续通过 NCBI 批量查询补齐。

### 3. assembly_manifest.tsv

用途：补充 Assembly / 组装版本信息。

建议字段：

```text
accession
assembly_name
display_name
assembly_code
assembly_level
chromosome_count
genome_size_display
reference_genome
bioproject
reference
is_default
description
```

主要来源：

```text
NCBI Assembly：GCA/GCF 编号、组装级别、染色体数、BioProject
论文或项目说明：参考基因组，例如 Nipponbare、MH63、9311
文件名 / 目录名：组装版本名称
课题组分析记录：组装方法、版本说明
```

注意：

```text
reference_genome 通常表示组装时参考了哪个已有基因组，这个信息 NCBI 不一定直接提供，很多时候需要从论文、项目说明或分析流程记录中补充。
```

### 4. annotation_manifest.tsv

用途：补充 Annotation / 注释版本信息。

建议字段：

```text
accession
assembly_name
annotation_name
display_name
annotation_code
source_name
release_version
method
is_default
description
```

主要来源：

```text
GFF / GTF 文件名
注释流程记录
Maker / PASA / Liftoff / Augustus 等注释方法
项目说明文档
课题组分析记录
```

注意：

```text
Annotation 信息通常不是 NCBI 自动能完整给出的，更多依赖内部分析流程和文件命名规范。
```

### 5. sample_manifest.tsv

用途：补充 Sample / 样本信息。

建议字段：

```text
sample_code
sample_name
species_code
accession
tissue
treatment
replicate
data_type
description
```

主要来源：

```text
SRA Run Selector
BioSample metadata
RNA-seq 实验设计表
课题组样本记录表
测序公司交付表
```

NCBI 或 SRA 中常见可用字段包括：

```text
tissue
library_strategy
platform
instrument
BioSample
Run
Experiment
```

### 6. raw_data_manifest.tsv

用途：人工登记原始数据文件。

建议字段：

```text
accession_code
sample_code
species_code
raw_data_type
sequencing_platform
file_role
cluster_name
file_path
file_size
md5
check_status
remark
```

主要来源：

```text
集群文件路径
课题组数据统计表
md5 校验文件
测序公司交付表
人工登记信息
```

注意：

```text
raw_data_manifest 主要反映课题组内部文件资产，不完全依赖 NCBI。
```

## 推荐补表流程

### 第一步：整理 Accession 清单

从数据库导出现有 Accession：

```bash
python manage.py shell -c "from files.models import Accession; print('\n'.join(Accession.objects.values_list('accession', flat=True)))" > accessions.txt
```

### 第二步：整理已有 NCBI 编号

从以下来源提取：

```text
raw_data_manifest.tsv
Accession.description
外部链接
文件名
课题组 Excel
已有页面中的 NCBI 链接
```

重点查找这些编号：

```text
PRJNA
SRP
SRX
SRR
SAMN
GCA
GCF
```

### 第三步：批量获取 NCBI metadata

推荐方式：

```text
1. NCBI SRA Run Selector 下载 CSV
2. NCBI Datasets CLI
3. Entrez Direct：esearch / efetch / esummary
```

不建议逐个打开网页复制。

### 第四步：生成候选 TSV

先生成候选文件，例如：

```text
dataset_manifest.candidate.tsv
assembly_manifest.candidate.tsv
sample_manifest.candidate.tsv
```

### 第五步：人工审核异常

人工主要审核：

```text
没有匹配到 NCBI 编号的 accession
一个 accession 对多个 BioProject 的情况
国家 / 地区缺失或不确定
reference_genome 不确定
材料名别名冲突
同一材料多个写法不一致
```

### 第六步：形成正式 TSV

审核完成后，再整理成正式 manifest：

```text
accession_manifest.tsv
assembly_manifest.tsv
annotation_manifest.tsv
dataset_manifest.tsv
sample_manifest.tsv
raw_data_manifest.tsv
```

### 第七步：dry-run 导入

正式导入前必须先 dry-run：

```bash
python manage.py import_xxx_manifest --input metadata/xxx_manifest.tsv --dry-run
```

重点检查：

```text
unmapped
warning
created_count
updated_count
skipped_count
```

### 第八步：正式导入与审计

确认 dry-run 没有明显问题后再执行正式导入：

```bash
python manage.py import_xxx_manifest --input metadata/xxx_manifest.tsv
```

导入后运行审计命令：

```bash
python manage.py audit_genome_transcriptome_readiness --output-dir audit_reports
python manage.py validate_new_file_structure
```

## 最现实的补充策略

当前阶段建议：

```text
1. 从 raw_data_manifest.normalized.tsv 提取已有 accession、文件路径、remark、SRA / BioProject 信息。
2. 从生产库已有 external link 中提取 SRP / PRJNA。
3. 批量生成 dataset_manifest 候选表。
4. 对缺失项再人工查 NCBI 或询问课题组。
5. 对 reference_genome、annotation method 这类内部分析信息，从分析记录中补。
```

人工只处理疑难项，不要处理全部数据。

## 总结

TSV 内容不应该完全靠人工逐条录入，而应该采用：

```text
NCBI 批量抓取 + 内部 Excel / 文件路径补充 + 人工审核异常
```

其中：

```text
NCBI 适合补 Project / Dataset / Sample / Assembly 编号
课题组表适合补材料名、物种、国家地区、样本说明
分析记录适合补 reference_genome、annotation method
集群文件适合补 raw_data_manifest
```

最终目标是让 TSV 成为标准化导入入口，而不是零散临时表。
