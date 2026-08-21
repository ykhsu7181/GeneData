# files tests

测试按职责组织，避免因开发阶段而复制同一业务断言。

| 目录 | 覆盖范围 | 推荐运行方式 |
| --- | --- | --- |
| `unit/` | 模型字段、枚举和文件关系服务 | `python manage.py test files.tests.unit --keepdb` |
| `api/` | 页面查询接口、下载接口和新查询入口 | `python manage.py test files.tests.api --keepdb` |
| `commands/` | 导入、扫描、审计和校验管理命令 | `python manage.py test files.tests.commands --keepdb` |
| `regression/` | GenomeFile 归档和历史兼容边界回归 | `python manage.py test files.tests.regression --keepdb` |

新增测试时：

1. 先在对应职责目录补充已有测试类，不为单个阶段创建重复文件。
2. 文件服务、下载和扫描只验证 `DataFile + FileRelation` 的 new-only 路径。
3. `GenomeFile` 仅能在归档、审计或迁移场景的测试中构造，不得作为业务查询结果断言。
4. 提交前至少运行受影响目录；跨接口改动运行 `python manage.py test files.tests --keepdb`。
