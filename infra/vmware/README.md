# 三台 VMware 虚拟机配置

这三个 `.vmx` 根据项目原集群整理，保留虚拟硬件版本 19、2 vCPU、4 GiB 内存、NAT 网卡和原磁盘控制器设置。宿主机上的 ISO 路径和原主机的 UUID、MAC 已移除，网卡地址由 VMware 生成。

| 节点 | VMware 配置 | 同目录需要的磁盘文件 |
| --- | --- | --- |
| NameNode | [namenode/hadoop.vmx](namenode/hadoop.vmx) | `hadoop.vmdk`、`hadoop-s001.vmdk` 至 `hadoop-s006.vmdk` |
| DataNode 1 | [datanode1/datanode1.vmx](datanode1/datanode1.vmx) | 该节点的 `hadoop-cl1.vmdk`、`hadoop-cl1-s001.vmdk` 至 `hadoop-cl1-s006.vmdk` |
| DataNode 2 | [datanode2/datanode2.vmx](datanode2/datanode2.vmx) | 该节点的 `hadoop-cl1.vmdk`、`hadoop-cl1-s001.vmdk` 至 `hadoop-cl1-s006.vmdk` |

`.vmx` 记录虚拟机的硬件和磁盘连接，操作系统和 HDFS 数据保存在虚拟磁盘里。已有授权的课程虚拟磁盘时，把对应的 `.vmx` 放进该节点的磁盘目录，用 VMware Workstation 打开。两台 DataNode 的磁盘文件同名，必须分别放在各自的目录。若课程镜像的 `.vmdk` 描述文件名不同，使用镜像原来的 `.vmx`，或核实匹配的磁盘后调整 `scsi0:0.fileName`。

首次启动后，按 [VMware 三节点复现指南](../../docs/vmware.md) 核对 IP、主机名、HDFS 和 YARN。拿到的是已经入湖、清洗的三节点磁盘时，使用下方的续跑流程。没有课程磁盘的同学可以按同一份指南新建三台 Ubuntu VM 并从官方数据源运行。

## 使用已清洗数据继续运行

1. 使用同一批次的三台 VM 磁盘，保留 NameNode 元数据和两台 DataNode 的数据块。把三台启动到同一个 NAT 网络，更新 hosts。已有 HDFS 数据时直接启动现有集群，无需格式化。
2. 在 NameNode 克隆或更新仓库，在仓库根目录以 `hadoop` 执行以下命令。确保 Hadoop、Spark、Hive 和 JDK 已安装，可用环境变量覆盖安装路径，详见 [部署说明](../../docs/deployment.md)。

```bash
bash scripts/resume-from-clean.sh --check
bash scripts/resume-from-clean.sh --run
```

`--check` 只读取 HDFS，核对三份原始文件和三个清洗结果目录。`--run` 建立 Hive 外部表并补齐离线统计、ALS 推荐和实时快照。执行过程中沿用已有的完整结果。若启动时已经存在 Streaming checkpoint 或批次目录，但缺少最终快照，请保留原状态并核对是否还是原 Kafka 主题；确认后可用 `pipeline/streaming/run-stage5.sh stream` 从原 checkpoint 继续。

3. 看到 `DASHBOARD_RESULTS_OK` 后，按 [连接现有集群](../../docs/deployment.md#连接现有集群) 打开看板。已有所有结果时也可以直接启动看板。若 Kafka broker 尚未启动，页面仍可从 HDFS 读取最近快照。

VMX 文件可随仓库克隆。包含 MovieLens 原始及清洗数据的磁盘由有权分发的课程渠道提供。持有同批镜像的同学可以跳过数据下载与清洗。 [MovieLens 数据使用许可](https://files.grouplens.org/datasets/movielens/ml-1m-README.txt)
