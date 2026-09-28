# GeneData JBrowse 2 阶段五部署执行单

## 1. 本阶段范围

阶段五负责以下内容：

1. 固定 JBrowse Web 版本为 `4.3.0`；
2. 在 Assembly 页面按后端状态控制“基因组浏览器”入口；
3. 新增内置浏览器页面，通过同源 iframe 加载 `/jbrowse2/`；
4. 使用后端生成的 JBrowse 配置，不向浏览器暴露服务器物理路径；
5. 准备静态应用构建脚本和 Nginx 示例配置。

本阶段不会在开发机上直接修改生产 Nginx，也不会覆盖生产现有发布目录。

## 2. 固定版本静态包

版本与校验值：

```text
JBrowse Web: 4.3.0
Release archive: jbrowse-web-v4.3.0.zip
SHA-256: a9d42417102ee088a1cbf85c6d857c1065d66984ea6c56f3115ef9dd56d76702
```

在生产服务器的项目目录执行：

```bash
cd /home/labuser/rdcheng/gd/django2
bash ../scripts/build_jbrowse2_web.sh \
  /home/labuser/rdcheng/gd/releases/jbrowse2-v4.3.0
```

如果生产代码部署结构中 `scripts` 与 `django2` 不在上述相对位置，应使用脚本的实际绝对路径。脚本要求输出目录不存在，并在下载、SHA-256 校验、解压和版本检查全部通过后才移动到最终目录。

只读核验：

```bash
cat /home/labuser/rdcheng/gd/releases/jbrowse2-v4.3.0/version.txt
sha256sum /home/labuser/rdcheng/gd/releases/jbrowse2-v4.3.0/index.html
find /home/labuser/rdcheng/gd/releases/jbrowse2-v4.3.0 \
  -maxdepth 2 -type f | head -20
```

## 3. Nginx 配置

参考仓库文件：

```text
deploy/nginx/genedata-jbrowse2.conf.example
```

由有 Nginx 管理权限的管理员完成：

1. 把示例中的三个 `location` 合并到 GeneData 所在 HTTPS `server` 块；
2. 确认 `/jbrowse2/` 指向固定版本静态目录；
3. 确认两个 `internal` 路径分别对应生产 `manual_files` 和 `derived_data`；
4. 运行 `nginx -t`；
5. 配置检查通过后执行平滑 reload。

不要把 `internal` 删除，否则用户可能绕过 Django 的可见性判断直接访问文件。

## 4. 发布前依赖

先在生产环境完成 IR64 索引实际生成：

```bash
cd /home/labuser/rdcheng/gd/django2

# 使用生产进程的 Python、settings 和必需环境变量执行；先 dry-run。
"$DJANGO_PYTHON" manage.py build_jbrowse_indexes \
  --assembly-id 1400 --dry-run \
  --settings=filemanager.settings_production

# 审核 dry-run 输出无误后再实际生成。
"$DJANGO_PYTHON" manage.py build_jbrowse_indexes \
  --assembly-id 1400 --apply \
  --settings=filemanager.settings_production
```

生产进程依赖的环境变量（特别是 `DJANGO_SECRET_KEY`）不能通过截图、日志或文档输出；应由现有进程管理方式安全注入。

## 5. 验证顺序

### 5.1 静态应用

```bash
curl -sS -o /dev/null -w 'jbrowse HTTP %{http_code}\n' \
  https://生产域名/jbrowse2/

curl -sS https://生产域名/jbrowse2/version.txt
```

预期首页为 `200`，版本为 `4.3.0`。

### 5.2 状态与配置 API

```bash
curl -sS https://生产域名/gd/api/files/assemblies/1400/jbrowse-status/
curl -sS https://生产域名/gd/api/files/assemblies/1400/jbrowse-config/
```

预期状态为 `ready` 或 `reference_only`。配置 JSON 中不得出现 `/home/`、`file_path` 或真实文件系统路径。

### 5.3 Range 请求

先从配置 JSON 取得 FASTA、`.fai`、`.gff.gz` 和 `.tbi` 的 API URL，再逐一验证：

```bash
curl -sS -D - -o /dev/null \
  -H 'Range: bytes=0-99' \
  https://生产域名/gd/api/files/browser-assets/数据文件ID/
```

预期响应包含：

```text
HTTP/1.1 206 Partial Content
Content-Range: bytes 0-99/...
Accept-Ranges: bytes
```

### 5.4 页面验收

1. 打开 IR64 Assembly 详情页；
2. 确认“基因组浏览器”按钮只在后端状态可用时启用；
3. 进入浏览器页面，确认参考序列和注释轨道加载；
4. 验证坐标跳转、缩放、拖动和 feature 点击；
5. 验证浏览器开发者工具中没有物理路径泄露；
6. 验证原有 Assembly、Annotation 和下载功能未回归。

## 6. 回滚

发生问题时按以下顺序回滚：

1. 回滚 Vue 静态文件以隐藏入口；
2. 将 `/jbrowse2/` 的 alias 恢复到上一固定版本目录；
3. 恢复 Nginx 配置并执行 `nginx -t` 后平滑 reload；
4. 保留 `derived_data` 索引与审计报告，暂不删除；
5. 不修改或删除生产 `manual_files` 原始文件。

## 7. 当前结论

开发侧页面、路由、状态门控、配置适配、固定版本构建流程和 Nginx 示例已准备。生产侧仍需完成 IR64 实际索引生成、Nginx 配置、Vue 发布以及 Range `206` 和页面验收，完成前不得标记阶段五生产验收通过。
