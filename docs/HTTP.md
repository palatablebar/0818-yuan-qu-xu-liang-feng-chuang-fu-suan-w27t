# 阶段接口

`POST /api/stages/<stage>` 接收 `multipart/form-data`。字段 `sample=dirty`、`sample=clean` 或 `file=<CSV>` 三选一。阶段为 `intake`、`prepare`、`calculate`、`policy`、`balance`。预览不入库。

`POST /api/runs` 接收同样的输入，执行全批并返回运行报告。`GET /api/runs` 返回最近 50 批。`GET /api/runs/<id>` 查询一批和当前复核状态。

`PATCH /api/runs/<id>` 接收 `revision`、`status` 和 `note`。状态使用 `APPROVED` 或 `HELD`。冲突返回 409，客户端读取新版本后重试。

缺测窗口的已到读数达到候选峰值时，`APPROVED` 返回 409 `UNRESOLVED_ISSUES`，`message` 指出业务分组与记录键，`details.blocking` 列出对应窗口。报告中的 `cases[].coverage` 保留缺测窗口依据，`balance.blocking` 汇总阻断分组。

`GET /api/runs/<id>/evidence` 下载内含运行清单、行号隔离、缺测覆盖、业务证据和复核信息的 JSON。
