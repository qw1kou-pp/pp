# 真实 GitHub 仓库兼容性验收设计

## 目标

建立一套直接访问真实 GitHub、可在本地和 CI 中运行的仓库验收系统，证明不同仓库能够完成仓库概览、固定 Commit 深度导入、RAG、Code Agent、来源隔离和历史隔离。

## 已确认约束

- 使用真实 GitHub，不使用离线仓库 Fixture。
- 通过 `GITHUB_TOKEN` 提供 GitHub Token。
- 每次从默认分支解析当时的最新 Commit，不预先写死 SHA。
- 一次验收运行内必须固定 `resolved_commit_sha`，后续文档、RAG、Agent 和历史必须与该 SHA 一致。
- 网络请求采用最多 3 次重试，退避时间为 1、2、4 秒；最终失败时整项验收失败。
- 本地支持单仓库、冒烟矩阵和完整矩阵。
- PR 运行 2 个冒烟仓库；每周和手动触发可运行完整矩阵。
- 首批仓库为 `psf/requests`、`fastapi/fastapi`、`pmndrs/zustand`、`fastapi/full-stack-fastapi-template`。

## 架构

验收系统由配置、数据模型、HTTP 客户端、流程运行器、断言、报告、pytest 入口和 CLI 组成。HTTP 客户端只负责请求；运行器负责编排完整流程；断言层只判断结果；报告层输出 JSON 与 Markdown。

## 范围隔离规则

仓库范围 RAG、Agent 和历史中的每条来源必须同时满足：

1. `repository_analysis_task_id` 等于当前任务 ID；
2. `source_commit_sha` 等于当前任务的 `resolved_commit_sha`；
3. 来源具有 `repository_relative_path` 或 `original_filename`。

普通知识库历史不得返回仓库任务历史，仓库 A 不得返回仓库 B 的来源或历史。

## CI 策略

- PR：运行 `requests` 与 `full-stack-fastapi-template`。
- 每周：运行完整 4 仓库矩阵。
- 手动：支持指定单仓库、冒烟矩阵或完整矩阵。
- 验收报告作为 GitHub Actions Artifact 上传。

## 阶段边界

任务十四只实现真实仓库兼容性、范围隔离和单次运行可复现性。Worker 故障注入与恢复验收属于任务十五；指标、日志、管理接口和部署监控属于任务十六。
