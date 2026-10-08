# GeneData b0a1ce8 生产发布包校验报告

## 1. 交付件

| 交付件 | 路径 |
|---|---|
| 完整发布包 | `.artifacts/releases/GeneData_b0a1ce8_20260929.zip` |
| 发布包 SHA-256 | `.artifacts/releases/GeneData_b0a1ce8_20260929.zip.sha256` |
| 包内逐文件清单 | `GeneData_b0a1ce8_20260929/SHA256SUMS` |
| 部署执行手册 | `docs/GeneData_生产环境JBrowse2完整部署执行手册_b0a1ce8.md` |
| 可重复打包脚本 | `scripts/build_production_release.ps1` |

## 2. 发布身份

- 来源提交：`b0a1ce81e0c57fd3519604e2f91a230dd4a3e2ee`
- 提交说明：`feat: add resumable JBrowse batch indexing`
- 生产基线：`557aa17`
- JBrowse Web：`4.3.0`
- ZIP 大小：`10,610,284` 字节
- ZIP SHA-256：`d71a6ea23e2bf6e4e5603911666543bb56ca8cdd4d0eabfbe48b01a754afe0cb`

## 3. 开发机已验证

| 项目 | 结果 | 证据 |
|---|---|---|
| PowerShell 打包脚本语法 | PASS | PowerShell AST 解析无错误 |
| 外层 ZIP SHA-256 | PASS | PowerShell `Get-FileHash` 与 `.zip.sha256` 一致 |
| Linux 外层 SHA-256 | PASS | WSL GNU `sha256sum -c` 返回 `OK` |
| 包内逐文件 SHA-256 | PASS | Windows 验证 `1151` 项全部一致 |
| Linux 包内 SHA-256 | PASS | WSL GNU `sha256sum -c SHA256SUMS` 成功 |
| 归档条目数 | PASS | `1155` |
| JBrowse 版本 | PASS | `version.txt` 为 `4.3.0` |
| 来源提交 | PASS | `RELEASE_INFO.txt` 为完整 `b0a1ce8...` 提交 |
| 生产运行时目录排除 | PASS | 未包含 `manual_files`、`derived_data`、日志、数据库、`.git` 和 `.artifacts` |
| JBrowse 上游演示数据排除 | PASS | 未包含 `test_data` |

## 4. 生产上传后必须重新执行

```bash
cd /home/labuser/rdcheng/gd/uploads
sha256sum -c GeneData_b0a1ce8_20260929.zip.sha256

unzip -q GeneData_b0a1ce8_20260929.zip \
  -d /home/labuser/rdcheng/gd/staging_b0a1ce8_20260929

cd /home/labuser/rdcheng/gd/staging_b0a1ce8_20260929/GeneData_b0a1ce8_20260929
sha256sum -c SHA256SUMS
cat RELEASE_INFO.txt
```

只有外层和包内校验均通过后，才能进入备份、配置合并和代码切换阶段。

## 5. 生产待验证

以下项目尚未在生产服务器执行，不得标记为 PASS：

- 生产数据库一致性备份；
- 生产 Django `check` 和 migration plan；
- Nginx 配置合并、`nginx -t` 和 reload；
- GeneData 2025 服务切换；
- JBrowse Web HTTP 200；
- IR64 dry-run、apply、动态配置和 Range 206；
- 全量 dry-run 及异常审核；
- 全量 apply 和最终 checkpoint；
- Assembly、Annotation、下载等旧功能回归；
- 浏览器端 JBrowse 最终验收。
