# 已完成的项目结果

默认启动读取 [completed-results.json.gz](completed-results.json.gz)。它从本项目已验收的 Hadoop 集群导出，包含离线统计、影片排行、最近 30 个回放窗口，以及 6,040 位用户共 60,400 条预生成的 ALS 推荐。片名和类型随推荐结果保存，查看时无需读取源数据。推荐结果保留原用户编号、名次及模型预测分。

本目录提供展示派生结果。完整数据流水线和原始数据获取方式见 [部署与复现](../../docs/deployment.md)。

维护者如需更新快照，在 Python 3.11 环境安装集群依赖、配置 WebHDFS 后，从仓库根目录执行：

```bash
python -m pip install -r dashboard/requirements-cluster.txt
python scripts/export-snapshot.py
python verification/verify_snapshot.py
```

导出脚本读取已经写入 HDFS 的结果。训练、Kafka 回放以及 Streaming 作业由原流水线负责。
