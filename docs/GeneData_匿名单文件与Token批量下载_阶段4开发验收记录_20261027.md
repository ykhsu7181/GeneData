# GeneData 匿名单文件与 Token 批量下载：阶段 4 开发验收记录

## 1. 阶段结论

阶段 4 开发环境验收通过。后端、前端、独立 CLI、wheel 安装和本地模拟 HTTP 工作流均通过验证，可以进入阶段 5 生产灰度准备。

本结论只覆盖开发环境，不代表生产环境、HPC 登录节点或 100 文件真实批次已经验收。

## 2. 验收对象

- 分支：`feature/public-file-access-v2`
- 阶段 3 提交：`949420847f49531c03fd0b1933b8b4310483d8f7`
- CLI wheel：`genedata_cli-0.1.0-py3-none-any.whl`
- wheel SHA-256：`20e10fa27ce47c182ee8540f1ba97cd7721ef132d98ecc161c1f3a5d50242473`
- 干净安装环境：新建 Python 3.13.2 虚拟环境，仅安装 `pip==24.3.1` 和 `genedata-cli==0.1.0`

## 3. CLI 源码验证

源码单元测试结果：

```text
Ran 17 tests
OK (skipped=5)
```

其中 12 个单元测试通过；5 个“已安装 wheel HTTP 集成测试”在源码模式按设计跳过，随后在干净安装环境单独执行。

## 4. 干净 wheel 安装验证

安装命令使用本地 wheel 和 `--no-index`，未从网络补充依赖：

```text
python -m pip install --no-index genedata_cli-0.1.0-py3-none-any.whl
```

结果：

- `genedata-cli==0.1.0` 安装成功；
- 无第三方运行依赖；
- `python -m genedata_cli --version` 输出 `genedata 0.1.0`；
- 安装生成的 `genedata` 控制台命令可以显示帮助。

## 5. 模拟 HTTP 集成验收

在已安装 wheel 的全新环境中，以真实子进程调用 CLI，并与本地 `ThreadingHTTPServer` 通信。5 组集成测试全部通过：

1. CLI 帮助、公开文件查询、文件详情和匿名单文件下载；
2. Token 批次预览，以及 FASTA 与 FAI 的权威 Manifest 批量下载；
3. HTTP 响应中断后保留 `.part`，第二次请求使用 Range 恢复；
4. SHA-256 不匹配时返回失败、不生成最终文件并保留 `.part`；
5. 401、403、409 和 429 返回稳定退出码，标准输出和错误输出不包含 Token。

首次集成运行中有一个测试断言顺序错误：测试在执行第二次恢复并完成原子改名后才检查 `.part`。调整为“第一次失败后检查 `.part`，再执行恢复”后通过；CLI 源码无需修改。

## 6. 后端完整回归

执行：

```text
python manage.py test files --verbosity 1
```

结果：

```text
Ran 520 tests in 26.061s
OK (skipped=1)
```

保留的现有非阻断警告：

- MySQL 不支持 `Annotation` 和 `Assembly` 的条件唯一约束；
- `DataFile.file_path` 唯一 `CharField` 长度可能超过 MySQL 索引限制；
- 部分旧模型校验器输出 Decimal 类型提示。

## 7. 前端完整回归

- `npm test`：188 个通过，0 个失败；
- `npm run lint`：通过；
- `npm run build`：通过；
- 构建哈希：`a4b86d5b8bf24572`。

保留的现有非阻断警告：

- `accessionViews.js` 的 Node 模块类型提示；
- vendor 和入口包超过 Vue CLI 建议体积，入口约 1.59 MiB。

## 8. 阶段 5 前仍需完成

- 制作可部署代码包和前端构建包；
- 在生产先保持 `GENEDATA_ALLOW_ANONYMOUS_PUBLIC_CONTENT=false`；
- 验证旧 Token 单文件下载无回归后再开启匿名开关；
- 对生产 FASTA、FAI 和非 FASTA 文件执行匿名 GET、HEAD、Range 和 SHA-256 抽样；
- 用真实 Token 验证 100 文件批次和服务器权威 Manifest；
- 在 HPC 登录节点安装 wheel，下载到共享目录，并由计算节点只读访问；
- 观察匿名/Token 限流、Nginx 日志、错误率和带宽；
- 验证关闭功能开关可以恢复原 Token 策略。
