# 部署与复现

只需使用已完成结果时，请按 [README 快速启动](../README.md#快速启动)。以下步骤用于接入集群或重跑流水线。

原集群使用 Hadoop 3.2.0、Spark 3.1.2（Scala 2.12）、Hive 3.1.2 和 Kafka 3.9.2，计算任务由 YARN 调度。Flask 已在 Python 3.11 验证。准备能访问彼此的 NameNode、DataNode 和 YARN，检查 SSH、主机名和时间同步，并确保 Hadoop 客户端配置与集群一致。

如果三台虚拟机尚未准备好，先执行 [VMware 三节点搭建指南](vmware.md)。

## 在集群上生成数据与结果

在仓库根目录执行。调整 Hadoop、Spark 和 Hive 的安装路径，下面的例子使用 NameNode 上常见的安装目录。

```bash
export HADOOP_HOME="$HOME/hadoop-3.2.0"
export HADOOP_CONF_DIR="$HADOOP_HOME/etc/hadoop"
export SPARK_HOME="$HOME/spark-3.1.2-bin-hadoop3.2"
export HIVE_HOME="$HOME/software/apache-hive-3.1.2-bin"
export MOVIELENS_HDFS_BASE=hdfs://namenode:9000/movie

"$HADOOP_HOME/bin/hdfs" dfsadmin -report
"$HADOOP_HOME/bin/yarn" node -list
```

从 [GroupLens](https://grouplens.org/datasets/movielens/1m/) 下载并解压 MovieLens 1M。下面的命令需在 NameNode 的仓库目录执行，并把数据路径替换为包含 `ratings.dat`、`movies.dat` 和 `users.dat` 的目录。

```bash
bash pipeline/ingest/load_raw.sh /path/to/ml-1m
"$SPARK_HOME/bin/spark-shell" --master yarn --deploy-mode client \
  --driver-memory 1g --num-executors 1 --executor-cores 1 --executor-memory 1g \
  --conf spark.sql.shuffle.partitions=8 --conf spark.sql.catalogImplementation=in-memory \
  -i pipeline/ingest/clean.scala </dev/null
"$HIVE_HOME/bin/hive" --hivevar movie_root="$MOVIELENS_HDFS_BASE" -f pipeline/sql/tables.sql
bash pipeline/offline/run-stage3-offline.sh
```

继续在同一 Bash 会话执行 ALS。第一次依次使用 `train` 和 `recommend`；已有模型和推荐时可用 `query` 检查指定用户。

```bash
run_als() {
  MOVIELENS_ALS_ACTION="$1" "$SPARK_HOME/bin/spark-shell" --master yarn --deploy-mode client \
    --driver-memory 1g --num-executors 1 --executor-cores 1 --executor-memory 1g \
    --conf spark.task.maxDirectResultSize=16m --conf spark.sql.shuffle.partitions=8 \
    --conf spark.sql.catalogImplementation=in-memory -i pipeline/als/train_als.scala </dev/null
}
run_als train
run_als recommend
MOVIELENS_ALS_USER_ID=1 run_als query
```

Kafka 脚本支持 `prepare`、`replay`、`stream`、`follow`。`stream` 在历史消息消费完成后退出，`follow` 用于持续等待新消息。已有 broker 时可用 `MOVIELENS_KAFKA_BOOTSTRAP` 指定地址。首次安装 Kafka 的机器需要访问 Apache 存档，connector 从 Maven Central 获取。

```bash
bash scripts/fetch-streaming-deps.sh
bash pipeline/streaming/run-stage5.sh prepare
bash pipeline/streaming/run-stage5.sh replay
bash pipeline/streaming/run-stage5.sh stream
bash verification/verify_hive.sh
```

输出路径默认为 `/movie/clean`、`/movie/model/als`、`/movie/result/offline`、`/movie/result/recommendations` 和 `/movie/result/realtime`。清洗和模型训练会检查目标目录是否已存在。保留原环境结果时，先核验已有产物，重跑请使用独立环境。用于看板的 HDFS 项目目录为 `/movie`。

## 连接现有集群

已有全部 HDFS 结果时，只需启动集群和 Flask。可跳过本页的数据处理、训练与回放步骤。Windows PowerShell 在仓库根目录执行，三个 IP 使用各虚拟机的实际地址：

```powershell
py -3.11 -m venv .venv
& .\.venv\Scripts\python.exe -m pip install -r dashboard/requirements-cluster.txt
$env:MOVIELENS_WEBHDFS = 'http://<NameNode-IP>:9870/webhdfs/v1'
$env:MOVIELENS_DATANODES = '{"datanode1":"<DataNode1-IP>","datanode2":"<DataNode2-IP>"}'
$env:MOVIELENS_KAFKA_BOOTSTRAP = '<NameNode-IP>:9092'
& .\.venv\Scripts\python.exe dashboard/app.py --mode cluster --port 5066
```

Linux 使用 `python3 -m venv .venv`、`.venv/bin/python` 和 `export` 设置对应环境变量。设置了 `MOVIELENS_WEBHDFS` 时，直接运行 `dashboard/app.py` 也会使用集群模式。

## 验证看板

按 [连接现有集群](#连接现有集群) 启动 Flask，在浏览器确认总览、用户 1 推荐和快照。WebHDFS 会把文件请求重定向到 DataNode，因此 Flask 所在机器要能访问 NameNode 的 9870 端口和两台 DataNode 的 9864 端口。使用 `MOVIELENS_DATANODES` 配置 DataNode 名称到地址的映射。

完整浏览器回归需要 Edge、Node.js 和 Playwright Core，以及一个数据量与原 MovieLens 1M 相同的项目环境。先启动用户看板服务，再运行以下命令。需要时使用 `MOVIELENS_PYTHON` 指向安装 Flask 依赖的 Python 可执行文件。脚本另起 5067 端口模拟 Kafka 断开。

```bash
npm install --no-save playwright-core
node verification/verify_browser.cjs
```

采集 Kafka 校验摘要可使用 Kafka 发行版客户端库和 JDK 17，运行 `java -cp "/path/to/kafka/libs/*" verification/VerifyKafka.java namenode:9092`。GitHub Actions 独立检查源码语法和 Flask 路由，集群联调按此文档执行。
