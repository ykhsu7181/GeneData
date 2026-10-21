# GeneData 外部工具数据 API Phase 0 测试设计

## 1. 范围与基线

- 实施分支：`feature/external-tool-data-api-v1`
- 固定基线：`feat/homepage-portal-redesign@efb1448b996b82fe31e9275563479fa5cd7003b9`
- 本阶段验证数据访问模型、Token 能力、统一访问决策、受保护路径解析及运营管理命令。
- 本阶段不实现 `/gd/api/v1/` HTTP 端点，不声称 Nginx Range、下载或生产部署已经通过。

## 2. 核心不变量

1. 迁移后现有 `DataFile` 默认为 `inherited + draft`，不会自动公开。
2. 文件必须同时满足 `is_current`、`released`、`published_at` 和有效 SHA-256 才能进入访问决策。
3. 文件策略与全部直接关联 Dataset 使用最小权限优先；任一私有、未发布或损坏关系均使决策失败关闭。
4. 公开元数据可以匿名读取；文件内容、序列和 Manifest 分别要求独立 Token scope。
5. internal 文件只允许 internal tier Token；private 文件不通过当前公共 API Token 开放。
6. Token 明文只在签发时返回一次，数据库只保存 HMAC-SHA256 摘要。
7. 物理文件必须位于配置逻辑根的真实路径内；符号链接不能逃逸允许根。
8. 多个根嵌套时选择最具体根，避免生成错误的 Nginx internal URI。

## 3. 已实现测试矩阵

### 3.1 模型与 Token

| 场景 | 预期 |
|---|---|
| 新建 DataFile | `inherited + draft` |
| 64 位十六进制 SHA-256 | 生成 `sha256:<digest>` 内容版本 |
| 非十六进制摘要 | 不生成内容版本 |
| Token 签发 | 返回一次明文，数据库只保存摘要 |
| 重复 scope | 去重并稳定排序 |
| 未知 scope | 拒绝签发 |
| Token 密钥被修改 | 鉴权失败 |
| Token 过期或撤销 | 鉴权失败 |

### 3.2 访问决策

| 场景 | 预期 |
|---|---|
| draft、withdrawn 或非 current 文件 | 拒绝 |
| 缺少发布时间或可信 SHA-256 | 拒绝 |
| released public Dataset 的元数据 | 允许匿名 |
| public 文件内容 | 必须具有 `file:read` |
| sequence/manifest | 分别要求 `sequence:read`/`dataset:manifest` |
| internal Dataset + public tier Token | 拒绝 |
| internal Dataset + internal tier Token | 允许 |
| 文件显式 private + public Dataset | private 获胜，拒绝 |
| 同一文件关联 public 和 private Dataset | private 获胜，拒绝 |
| inherited 但无 Dataset | 拒绝 |
| 显式 public 且无 Dataset | 在完成文件发布门禁后允许 |
| Dataset 未 released | 拒绝 |
| Dataset 关系 ID 损坏 | 失败关闭 |

### 3.3 路径决策

| 场景 | 预期 |
|---|---|
| 文件位于允许根 | 生成 URL 编码后的 internal URI |
| 文件位于根外 | 拒绝 |
| 文件不存在 | 拒绝 |
| 符号链接指向根外 | 拒绝 |
| 逻辑根嵌套 | 使用最具体的根 |

### 3.4 运营闭环

| 场景 | 预期 |
|---|---|
| 访问审计 | 只读并输出策略冲突、路径、SHA-256、FAI 与 ready/blocked 明细 |
| SHA-256 默认运行 | dry-run，不写数据库 |
| SHA-256 apply 后重跑 | 已完成项跳过，可续跑 |
| 根外文件 | 不计算摘要，报告失败 |
| 发布 dry-run | 验证清单但不改变状态 |
| 发布清单任一行失败 | 整批不发布，并保留 TSV |
| genome FASTA 无新鲜 FAI | 阻止发布 |
| Token dry-run | 不创建凭证 |
| Token apply | 明文只返回一次，列表不显示明文或摘要 |
| Token 撤销 | dry-run 不写；apply 后立即鉴权失败 |

## 4. 验证命令

```powershell
cd django2
python manage.py makemigrations --check --dry-run
python manage.py test `
  files.tests.unit.test_data_access_models `
  files.tests.unit.test_datafile_access_service `
  files.tests.commands.test_external_data_operations `
  --noinput
```

完成定向验证后运行：

```powershell
python manage.py test files --noinput
```

## 5. 后续阶段测试，不计入 Phase 0 通过项

- Bearer Token HTTP authentication 与稳定错误码。
- Metadata、Content、Manifest 和 Region API 契约测试。
- Django 返回 `X-Accel-Redirect` 的集成测试。
- 真实 Nginx 的 `200/206/416`、HEAD 和 `curl -C -` 续传测试。
- 生产数据库迁移演练、回滚和既有 Vue 页面回归。
