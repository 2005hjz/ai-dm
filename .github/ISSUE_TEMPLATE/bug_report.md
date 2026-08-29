---
name: Bug Report
about: 提交缺陷,帮助定位与修复
title: "[BUG] 简洁描述缺陷现象"
labels: [bug]
assignees: ''
---

## 现象 (Observation)
> 缺陷的客观表现,带复现步骤或截图。

- 期望行为:
- 实际行为:

## 复现步骤 (Steps to Reproduce)
1. 
2. 
3. 

## 环境 (Environment)
- 提供方:mock / deepseek / remote
- 浏览器:Chrome / Edge / ...
- Python 版本:3.12
- 容器化:宿主机 / Docker

## 日志与轨迹
- server.err.log 关键片段:
- API 返回状态码:200 / 429 / 422 / 500

## 严重级别
- [ ] P0 阻塞主流程  [ ] P1 高  [ ] P2 中  [ ] P3 低

## 关联测试
- 对应 BDD 场景:`tests/bdd/features/...`
- 单元测试:`tests/unit/...`