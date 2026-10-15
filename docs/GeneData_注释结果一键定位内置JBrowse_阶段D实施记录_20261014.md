# GeneData：从注释结果一键定位内置 JBrowse 阶段 D 实施记录

> 开始日期：2026-10-14
> 当前状态：**阶段 D 的开发环境验证已完成并通过；生产环境验证尚未开始。**
> 环境边界：本轮只使用本机开发数据库和内存测试数据库，没有连接生产环境，没有对 Assembly 93/1400 执行回填。

## 1. 第一轮回归发现

原状态接口中的 `status=ready`、`annotation_ready=true` 只表示 FASTA/FAI 和 GFF3/TBI 可供 JBrowse 浏览，不证明以下一键定位专用依赖已经就绪：

- 当前 Annotation 的特征索引；
- 当前 Assembly 的 refName 映射及其 FASTA/FAI 指纹。

阶段 C 前端仅依据轨道状态启用按钮，因此映射缺失时按钮可能先启用，点击后定位 API 才返回 503。数据不会被错误定位，但交互门禁不完整。

## 2. 已完成修正

### 2.1 独立定位就绪状态

`jbrowse-status` 响应新增：

```json
{
  "location_ready": true,
  "location_status": "ready"
}
```

轨道未就绪时 `location_status=jbrowse_not_ready`；特征索引、映射缺失或过期时返回对应稳定状态，但不改变原有 `status` 的轨道浏览语义。这样普通 Assembly 浏览器仍可按原状态工作，一键定位入口则采用更严格的门禁。

前端现在同时要求：

```text
status=ready
annotation_ready=true
location_ready=true
feature_id 为正整数
```

任一条件不满足，按钮保持禁用。

### 2.2 跨接口集成回归

新增集成用例按真实调用顺序验证：

1. `jbrowse-status` 返回轨道与定位均 ready；
2. `annotation-data` 返回稳定 `feature_id`；
3. `jbrowse-location` 将 `chr1` 映射为 `GWHESLA00000001` 并返回规范 `loc`；
4. `jbrowse-config` 的 Assembly 名称和轨道 ID 与定位响应一致；
5. FASTA、FAI、GFF3、TBI 四个资产 URL 均为受保护 API URL；
6. 资产响应具有 `Accept-Ranges` 和受保护内部转发头；
7. 配置响应不包含测试物理目录。

## 3. 自动化验证

```text
python manage.py check
System check identified no issues

python manage.py makemigrations --check --dry-run files
No changes detected in app 'files'

python manage.py test files --settings=filemanager.settings_sqlite_test --noinput
Ran 397 tests: OK (skipped=2)

npm test
173 tests passed, 0 failed

npm run lint
通过

npm run build
退出码 0，生产构建完成
```

构建仍只有项目既有的 bundle/entrypoint 体积警告。

## 4. 开发环境真实联调

### 4.1 WSL 与完整开发栈

主机资源恢复后，下列命令正常返回默认路由：

```text
default via 172.17.192.1 dev eth0 proto kernel
```

随后执行：

```powershell
.\scripts\start_jbrowse_dev.ps1 -SkipNpmInstall
```

完整开发栈启动成功：Vue 为 `http://localhost:8080/`，Django 为 `http://localhost:2025/`，Nginx/JBrowse 的 `/jbrowse2/version.txt` 返回 4.3.0。首次 Vue 编译超过原脚本的 60 秒等待上限，因此将 Vue HTTP 就绪等待调整为 180 秒；这只扩大冷启动容忍时间，不改变服务配置。

### 4.2 开发 refName 映射

只对本地开发 Assembly 131 执行回填，未连接或修改生产 Assembly 93/1400。dry-run 结果为：

```text
reference_count=12
alias_count=12
ambiguous_alias_count=0
ready_for_build
```

确认真实 FASTA/FAI 均可读后执行 apply，生成的映射注册为 `DataFile 152`，路径为：

```text
/home/ykxu/genedata-jbrowse-runtime/derived/jbrowse/assemblies/assembly-131/refname-aliases.json
```

回填后 Assembly 131 / Annotation 131 的状态为：

```json
{
  "status": "ready",
  "annotation_ready": true,
  "location_ready": true,
  "location_status": "ready",
  "assembly_name": "assembly-131",
  "track_ids": ["annotation-131-features"]
}
```

### 4.3 跨接口与受保护资产

开发注释查询返回首条真实记录 `feature_id=1`、`seqid=Chr07`、`start=25730949`、`end=25731275`。定位 API 返回：

```text
loc=Chr07:25730449-25731775
refName=Chr07
assembly_name=assembly-131
track_id=annotation-131-features
```

配置接口中的 Assembly 名称和轨道 ID 与定位响应一致。通过 Vue → Nginx → Django 完整代理链路，分别对 FASTA 14、FAI 149、GFF3 150、TBI 151 请求 `bytes=0-63`，四个响应均为 HTTP 206、各返回 64 字节，`Content-Range` 正确。外部响应未暴露内部转发头，配置 JSON 也未包含物理路径。

### 4.4 真实浏览器页面

从以下真实注释上下文开始：

```text
/annotation?accession=IR64&assembly=131&annotation=131&chromosome=Chr07
```

首行“在基因组浏览器中查看”按钮处于可用状态。点击后页面进入 Assembly 131 浏览器，iframe 初始 URL 与“在新窗口打开”的链接完全相同，均包含：

```text
assembly=assembly-131
loc=Chr07:25730449-25731775
tracks=annotation-131-features
```

固定版 JBrowse 4.3.0 实际渲染出 `Chr07:25,730,449..25,731,775`，显示 `IR64 annotation` 轨道及目标 `gene:OsIR64_07g0022220`。新窗口成功打开相同入口；JBrowse 加载后按自身机制将地址规范化为带 `session=local-...` 的本地会话 URL。点击“返回”后，浏览器精确恢复上述 `accession/assembly/annotation/chromosome` 上下文。

截图证据保存在 `.artifacts/stage-d-jbrowse.png`；自动化浏览器检查脚本保存在 `.artifacts/stage_d_browser_check.cjs`。

## 5. 阶段结论与剩余边界

阶段 D 的开发环境目标已经完成：失败关闭、完整回归、真实 206 Range、目标特征可见性、新窗口和返回上下文均有证据。生产环境未执行任何映射回填、文件注册、服务重启或页面验证。

下一步应进入生产前准备：先备份并核对 Assembly 1400/93 的真实文件关系，在生产环境仅执行映射 dry-run；审阅结果无歧义且指纹匹配后，才分别 apply 并按同一清单验证状态、定位、配置、四类 Range、页面与回滚证据。开发环境通过不得替代生产验收。
