# GeneData 匿名单文件与 Token 批量下载：阶段 0 基线记录

## 1. 阶段结论

阶段 0 已完成。后续实现统一从独立分支 `feature/public-file-access-v2` 开始，不在已有功能分支或主工作区中混入改动。

- 基线日期：2026-10-27
- 独立工作树：`D:\gene_manage_system\public_file_access_v2_worktree`
- 基线提交：`44d877afb128d0004018b903b65d12e36251a1fd`
- 基线文档提交：`44d877a docs: define anonymous single-file and token batch downloads`
- 实施依据：`docs/GeneData_匿名单文件与Token批量下载_实施方案.md`
- 阶段 1 代码改动：尚未开始

## 2. 本阶段边界

本阶段只建立可复现的集成起点并验证现有测试，不修改下载鉴权、批量任务、CLI 或页面业务逻辑。

计划中的目标行为仍为：

1. 已公开的单个文件允许匿名下载；
2. 批量下载继续要求具备相应权限的 Token；
3. 页面可导出用户选择的 TSV；
4. CLI 只采信 TSV 中的 `file_code`，由服务器重新解析权限、状态、下载地址和 SHA-256；
5. 批次与服务器清单保持不可变、可审计。

以上是待实现需求，不代表生产环境已完成。

## 3. 基线验证结果

### 3.1 后端

执行范围：

```text
files.tests.unit.test_datafile_access_service
files.tests.api.test_external_file_api_v1
files.tests.api.test_external_file_catalog_api_v1
files.tests.api.test_external_file_batch_api_v1
```

结果：运行 42 个测试，全部通过，跳过 1 个。

现有测试所固定的当前行为包括：文件内容接口使用 `file:read` Token；批量接口无 Token 返回 401，具备批量权限的 Token 可创建并读取批次。匿名单文件下载是后续阶段需要引入并重新测试的行为。

已存在的非阻断警告：

- 当前测试数据库不支持 `Annotation` 和 `Assembly` 上的条件唯一约束；
- `DataFile.file_path` 的唯一 `CharField` 长度超过部分数据库索引限制。

### 3.2 前端

- `npm test`：184 个测试通过，0 个失败；
- `npm run lint`：通过；
- `npm run build`：通过，构建哈希 `9da6840958d79d37`。

已存在的非阻断警告：

- `src/services/accessionViews.js` 触发 Node 模块类型提示；
- 构建产物存在体积告警，入口约 1.59 MiB；
- `vue-i18n` v9 已进入停止维护状态。

### 3.3 工具链

- Python：3.13.2
- Node.js：v25.8.0
- npm：11.11.0

`npm ci` 可成功完成，但依赖声明尚未覆盖 Node.js 25，出现 engine 警告。依赖审计报告为 60 个漏洞（3 low、20 moderate、33 high、4 critical）。阶段 0 不执行自动修复，以免把无关升级或破坏性依赖变更混入本需求；该风险需另行评估和治理。

## 4. 阶段 1 进入条件

阶段 1 应在本分支上先实现并验证“公开单文件匿名下载”，同时保持以下安全边界：

- 只有满足公开发布条件的文件可以匿名获取；
- 草稿、受限、继承后仍非公开或物理文件不可用的记录不得匿名下载；
- Range 请求、响应头、文件名和审计行为不能退化；
- 批量 API 的 Token 要求不得放宽；
- 新增单元测试、API 测试，并重复运行本记录中的回归范围。
