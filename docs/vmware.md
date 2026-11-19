# VMware 三节点复现指南

同学从公开仓库获取代码和配置，从 GroupLens 获取 MovieLens 1M，然后在自己的虚拟机上生成数据、模型和快照。有课程老师已授权分发的三节点镜像时，可以走第 1 节的导入路径。新装虚拟机走第 2 节。验证通过后，两条路径都从第 3 节继续。

## 1. 导入已有课程镜像

1. 将三台虚拟机分别解压到独立目录。每台保留虚拟磁盘描述文件及其全部 `-s001.vmdk` 等磁盘分片。已有可用的 `.vmx` 时可直接打开。缺少配置时，从下表取对应文件并放到该节点的磁盘目录。其他批次的课程镜像以实际磁盘描述文件名为准。 [磁盘对应表](../infra/vmware/README.md)

   | 角色 | VMware 入口文件 |
   | --- | --- |
   | NameNode、ResourceManager、Kafka | [namenode/hadoop.vmx](../infra/vmware/namenode/hadoop.vmx) |
   | DataNode、NodeManager | [datanode1/datanode1.vmx](../infra/vmware/datanode1/datanode1.vmx) |
   | DataNode、NodeManager | [datanode2/datanode2.vmx](../infra/vmware/datanode2/datanode2.vmx) |

2. 在 VMware Workstation 依次打开三个 `.vmx`。把网卡连到同一个 NAT 网络（通常是 VMnet8）。复制到另一台主机时，若弹出提示，选择 **I copied it** 并重新核对 MAC 对应的地址。已有镜像迁移时应从完全关机的副本复制。 [VMware 复制说明](https://knowledge.broadcom.com/external/article/310359/copy-workstation-virtual-machine-from-on.html)
3. 进入三台 Linux 虚拟机，运行 `hostname` 和 `ip -4 -o addr show scope global` 记录实际地址，修正三台的 `/etc/hosts`。根据第 2 节检查节点名称、地址解析和 SSH，替换课程镜像里不再使用的个人登录密钥和共享目录。
4. 使用镜像既有的 Hadoop 安装路径和数据目录。如果镜像已经有 HDFS 元数据，直接启动或检查状态。已有集群无需格式化 NameNode。Kafka 迁移后确认 broker 广告地址可从三个节点和宿主机访问。

## 2. 从三台 Ubuntu 虚拟机搭建

### 2.1 节点、资源和网络

在 Workstation 新建三台 x86-64 Ubuntu VM，每台设为 2 vCPU、4 GB RAM，建议给每台至少 25 GiB 磁盘空间，并给 Windows 宿主机预留足够内存。三台网卡接到同一个 NAT 网络。VM 使用同名的普通 Linux 用户 `hadoop`，管理员用 `sudo` 处理系统设置。

| 主机名 | 服务 | 包的安装位置 |
| --- | --- | --- |
| `namenode` | NameNode、SecondaryNameNode、ResourceManager、Spark 提交端、Hive CLI、Kafka | Hadoop、Spark、Hive、JDK 8 |
| `datanode1` | DataNode、NodeManager | Hadoop、JDK 8 |
| `datanode2` | DataNode、NodeManager | Hadoop、JDK 8 |

每台以自己的节点名执行 `sudo hostnamectl set-hostname 节点名`。用实际 IPv4 地址填写三台的 `/etc/hosts`，删除旧的同名映射。如果 `127.0.1.1` 这一行包含集群节点名，也需去掉这个别名，确保三个节点名均解析到 NAT 网段地址。下面是填写格式。

```text
<NameNode-IP>   namenode
<DataNode1-IP>  datanode1
<DataNode2-IP>  datanode2
```

在三台安装 `openssh-server`、`git`、`curl`、`unzip` 和 Java 8 JDK。Java 可从 [Eclipse Temurin 8](https://adoptium.net/temurin/releases/?version=8) 获取 Linux x64 JDK，三台采用相同的实际安装路径。用 `java -version` 和 `javac -version` 核对。用 `timedatectl status` 检查时间同步。

在 NameNode 上以 `hadoop` 执行下面的命令。如果已有专用于本集群的 SSH 密钥，使用现有公钥。第一次复制公钥需要各 VM 的 `hadoop` 登录权限。

```bash
ssh-keygen -t ed25519
for node in namenode datanode1 datanode2; do
  getent ahostsv4 "$node"
  ssh-copy-id "hadoop@$node"
  ssh -o BatchMode=yes "hadoop@$node" hostname
done
```

推荐给 NAT 网络中的集群节点使用稳定地址。虚拟机地址变动后要同时更新三台的 hosts 和宿主机 Flask 配置。通过 VMware 的控制台改网卡时可直接观察实际新地址。

### 2.2 Hadoop 配置和启动

以 `hadoop` 在 NameNode 按[仓库首页的命令](../README.md#2-克隆仓库)克隆仓库并进入项目目录。在三台分别下载并解压 [Hadoop 3.2.0 发行包](https://archive.apache.org/dist/hadoop/common/hadoop-3.2.0/) 到 `~/hadoop-3.2.0`。NameNode 额外将 [Spark 3.1.2 Hadoop 3.2 发行包](https://archive.apache.org/dist/spark/spark-3.1.2/) 解压到 `~/spark-3.1.2-bin-hadoop3.2`，将 [Hive 3.1.2 发行包](https://archive.apache.org/dist/hive/hive-3.1.2/) 解压到 `~/software/apache-hive-3.1.2-bin`。

从仓库根目录在 NameNode 执行。确保这些配置只安装到本次新搭建的环境。

```bash
export HADOOP_HOME="$HOME/hadoop-3.2.0"
export HADOOP_CONF_DIR="$HADOOP_HOME/etc/hadoop"
cp infra/hadoop/* "$HADOOP_CONF_DIR/"
# 将 /path/to/jdk8 改成三台实际的相同路径
printf '\nexport JAVA_HOME=/path/to/jdk8\n' >> "$HADOOP_CONF_DIR/hadoop-env.sh"
for node in datanode1 datanode2; do
  scp infra/hadoop/* "$HADOOP_CONF_DIR/hadoop-env.sh" "$node:$HADOOP_CONF_DIR/"
done
```

在每台的 `hadoop` 登录 shell 设置以下变量，也可写进 `~/.profile` 下次登录继续使用。将 JDK 路径替换成实际值。两台 worker 使用同一份 `workers` 和 XML 配置。 [Hadoop 完全分布式配置](https://hadoop.apache.org/docs/r3.2.0/hadoop-project-dist/hadoop-common/ClusterSetup.html)

```bash
export JAVA_HOME=/path/to/jdk8
export HADOOP_HOME="$HOME/hadoop-3.2.0"
export HADOOP_CONF_DIR="$HADOOP_HOME/etc/hadoop"
export PATH="$JAVA_HOME/bin:$HADOOP_HOME/bin:$PATH"

# 仅在 NameNode 设置
export SPARK_HOME="$HOME/spark-3.1.2-bin-hadoop3.2"
export HIVE_HOME="$HOME/software/apache-hive-3.1.2-bin"
```

仅在**全新、尚无 HDFS 元数据**的 NameNode 上执行一次格式化。接着在 NameNode 启动 HDFS 和 YARN。

```bash
"$HADOOP_HOME/bin/hdfs" namenode -format movielens
"$HADOOP_HOME/sbin/start-dfs.sh"
"$HADOOP_HOME/sbin/start-yarn.sh"
"$HADOOP_HOME/bin/hdfs" dfsadmin -report
"$HADOOP_HOME/bin/yarn" node -list
```

HDFS 应报告 2 个在线 DataNode，YARN 应报告 2 个 `RUNNING` 的 NodeManager。Web 管理页默认为 `http://<NameNode-IP>:9870/` 和 `http://<NameNode-IP>:18088/`。副本数为 2。

### 2.3 NameNode 的 Hive 准备

在 NameNode 以 `hadoop` 新建 Hive 元数据。这里使用本机 Derby 支持课程 CLI 查询。将下面的 `/home/hadoop` 改为对应用户的绝对路径，保存为 `$HIVE_HOME/conf/hive-site.xml`。保证元数据目录在本机且使用绝对路径，同一时间只开一个使用该 Derby 库的 Hive 进程。

```xml
<?xml version="1.0"?>
<configuration>
  <property>
    <name>javax.jdo.option.ConnectionURL</name>
    <value>jdbc:derby:;databaseName=/home/hadoop/hive-metastore;create=true</value>
  </property>
  <property><name>hive.metastore.warehouse.dir</name><value>/user/hive/warehouse</value></property>
  <property><name>hive.execution.engine</name><value>mr</value></property>
</configuration>
```

```bash
"$HADOOP_HOME/bin/hdfs" dfs -mkdir -p /tmp /user/hive/warehouse
"$HADOOP_HOME/bin/hdfs" dfs -chmod 1777 /tmp
"$HIVE_HOME/bin/schematool" -dbType derby -initSchema
"$HIVE_HOME/bin/hive" -e 'SHOW DATABASES'
```

若首次执行遇到 Guava 的 `Preconditions.checkArgument` 兼容问题，可把新安装 Hive 自带的旧 Guava 移出 `lib`，将 Hadoop 发行包 `share/hadoop/common/lib` 中的 Guava 复制进 Hive 的 `lib`。先备份旧 jar，再重试。已初始化的 Derby 用 `schematool -dbType derby -info` 检查。 [Hive 兼容性记录](https://issues.apache.org/jira/browse/HIVE-22915)

## 3. 完成项目复现

1. 在 NameNode 进入仓库根目录，按 [部署与复现](deployment.md) 依次进行数据入湖、Hive、Spark SQL、ALS、Kafka 和 Streaming。Kafka 启动前确认 NAT IP 正确。多网卡时可显式设置 `MOVIELENS_BROKER_IP` 为 NameNode 的 NAT 地址。
2. Windows 宿主机在仓库根目录配置并启动 Flask。下列三处 IP 需要替换为 VM 的实际地址。宿主机通过 WebHDFS 读取文件时需要能访问 DataNode 的 HTTP 端口 9864。

```powershell
py -3.11 -m venv .venv
& .\.venv\Scripts\python.exe -m pip install -r dashboard/requirements.txt
$env:MOVIELENS_WEBHDFS = 'http://<NameNode-IP>:9870/webhdfs/v1'
$env:MOVIELENS_DATANODES = '{"datanode1":"<DataNode1-IP>","datanode2":"<DataNode2-IP>"}'
$env:MOVIELENS_KAFKA_BOOTSTRAP = '<NameNode-IP>:9092'
& .\.venv\Scripts\python.exe dashboard/app.py --port 5066
```

3. 按 [验收记录](verification.md) 核对关键口径，在自己的机器保留以下运行证据。

   - 2 个在线 DataNode、2 个运行中的 NodeManager。
   - `/movie/raw` 文件齐全，清洗后评分 1,000,209 条、电影 3,883 部、用户 6,040 位。
   - Hive 六表查询成功，日志末尾含 `HIVE_STAGE7_OK`。Scala 清洗和 ALS 日志可与 `yarn application -list -appStates FINISHED` 对照。
   - Kafka 回放日志包含 `KAFKA_REPLAY_OK`，流式结果日志包含 `KAFKA_STREAM_OK events=1000209 windows=55841`，最终 checkpoint 偏移为 1,000,209。
   - 本机看板显示十张图、用户 1 的十条推荐和近期窗口告警。断线通过 [浏览器回归脚本](../verification/verify_browser.cjs) 的独立测试实例验证。

## 4. 是否额外提供镜像

代码仓库已经包含源码、节点配置和复现步骤。如果老师或同学已有授权的课程镜像，可另行共享干净的基础环境以节省安装时间。公开仓库保持可直接克隆的体积。当前在用的环境包含 MovieLens 数据、行级清洗产物和 Kafka 消息，以及可能随系统盘一起复制的访问凭据。对外提供基础镜像前，使用单独副本清理这些内容，并实际在另一台电脑导入试跑。MovieLens 1M 由各成员从官方获取。 [数据许可](https://files.grouplens.org/datasets/movielens/ml-1m-README.txt) · [GitHub 大文件限制](https://docs.github.com/en/repositories/working-with-files/managing-large-files/about-large-files-on-github)

仓库已有原三节点运行和看板联调证据。新建三台 VM 的完整安装和同学电脑上的复现，由接手人按第 3 节记录验证结果。
