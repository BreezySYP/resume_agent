# 数据库迁移与备份指南

本目录存放数据库迁移/备份相关的**产物与操作文档**。当前状态：

- MySQL：已完成 baseline 捕获（`db/baseline/`），迁移/diff/rollback 流程见下文。
- Qdrant：暂未处理，规划见文末。

## 核心原则

1. **schema 以线上 MySQL 为准**，不依赖各服务里的 `schema.sql`（可能已过期）。baseline 来自
   `information_schema` + `SHOW CREATE TABLE`。
2. **只迁移有数据的表**。判断方式：`SELECT * FROM <table> LIMIT 1` 能取到行即有数据；
   空表暂不处理（需要时再用对应服务 schema.sql 重建）。
3. 任何 DDL 先备份、再执行；每次变更 `up.sql` / `down.sql` 成对提交；变更后刷新 baseline。

## 目录结构

```text
db/
├── README.md                 # 本指南
├── baseline/                 # 线上真实 schema 基线（MySQL）
│   ├── manifest.json         # 捕获时间、每张表的引擎/字符集/是否有数据/是否跳过
│   └── mydb/                 # 数据库名 = 目录名
│       ├── agent_memories.sql
│       └── ...               # 每张有数据的表一份 SHOW CREATE TABLE 快照
└── migrations/               # 迁移脚本：<时间戳>_<描述>/up.sql + down.sql
    ├── 20260908_0001_add_auth_tables/
    ├── 20260908_0002_add_conversation_threads/
    └── 20260910_0003_add_personal_access_tokens/
```

> 迁移脚本与基线是两套东西：基线记录“线上现在长什么样”，迁移描述“怎么从上一版变过来”。
> 新表（users / oauth_accounts / conversations）用迁移脚本管理；它们当前为空表，
> 按“空表暂不入基线”的约定暂不加入 `db/baseline/`。

## MySQL baseline（现状）

2026-09-08 从线上 MySQL（`mydb`）捕获：16 张基础表中 15 张有数据、已导出 DDL；
`history_job` 为空表，仅在 `manifest.json` 记录并跳过。

### 重新生成 baseline（schema 变更后）

有 mysql/mysqldump 客户端的主机（或 `docker exec` 进 MySQL 容器）上执行：

```bash
# 1) 全库结构快照（含视图/函数/触发器）
mysqldump --no-data --routines --triggers --single-transaction \
  -h "$MYSQL_URL" -P "$MYSQL_PORT" -u "$MYSQL_ROOT_USER" -p"$MYSQL_ROOT_PASSWORD" "$MYSQL_DATABASE" \
  > db/baseline/mydb_schema_dump.sql

# 2) 逐表检查是否有数据（空表不生成基线）
mysql -h "$MYSQL_URL" -P "$MYSQL_PORT" -u "$MYSQL_ROOT_USER" -p"$MYSQL_ROOT_PASSWORD" -N "$MYSQL_DATABASE" \
  -e "SELECT TABLE_NAME FROM information_schema.TABLES
      WHERE TABLE_SCHEMA = DATABASE() AND TABLE_TYPE = 'BASE TABLE'" |
while read -r t; do
  if mysql -h "$MYSQL_URL" -P "$MYSQL_PORT" -u "$MYSQL_ROOT_USER" -p"$MYSQL_ROOT_PASSWORD" -N \
      -e "SELECT * FROM \`$t\` LIMIT 1" "$MYSQL_DATABASE" >/dev/null 2>&1; then
    echo "HAS_DATA $t"
  else
    echo "EMPTY $t (skip)"
  fi
done

# 3) 有数据表逐个导出 DDL 到 db/baseline/mydb/<表>.sql
mysql -h "$MYSQL_URL" -P "$MYSQL_PORT" -u "$MYSQL_ROOT_USER" -p"$MYSQL_ROOT_PASSWORD" \
  --batch --raw -e "SHOW CREATE TABLE \`<表名>\`" "$MYSQL_DATABASE" | tail -n +2 > db/baseline/mydb/<表名>.sql
```

> 自动化的盘点/导出 CLI 之前放在 `src/schema_migration`，按“产物入库后清理一次性工具”的约定已删除；
> 上面的手工命令等价。若后续需要频繁重生成或做自动化 diff，可再补一个轻量脚本（见文末“可选工具”）。

## 迁移（migration）流程

1. 确认目标表属于“有数据”表；空表直接用 schema.sql 重建，不写迁移。
2. 在 `db/migrations/<YYYYMMDD_HHMMSS>_<描述>/` 下写 `up.sql` 与 `down.sql`。
3. 执行前先做该表备份（见“回滚与恢复”）。
4. 先小范围验证（先导库/测试库执行 up，再对拍行数与结构），再在生产执行。
5. 执行完刷新 `db/baseline/` 并提交，保证基线永远代表线上真实 schema。

## Diff（比较两个环境的 schema）

目标：比较 baseline（已提交的线上结构）与另一环境（如目标生产库、测试库）的真实结构。

```bash
# 目标环境导出单表 DDL
mysql -h "$TARGET_HOST" -u "$TARGET_USER" -p"$TARGET_PASSWORD" \
  --batch --raw -e "SHOW CREATE TABLE \`agent_memories\`" "$TARGET_DB" | tail -n +2 \
  > /tmp/target_agent_memories.sql

# 与基线对比
diff db/baseline/mydb/agent_memories.sql /tmp/target_agent_memories.sql
git diff --no-index db/baseline/mydb/agent_memories.sql /tmp/target_agent_memories.sql
```

diff 重点检查：列增删/顺序、类型与长度、`NULL/NOT NULL`、默认值、字符集与 collation
（本项目真实库大量使用 `utf8mb4_0900_ai_ci`，与部分 schema.sql 不一致）、索引、分区、`AUTO_INCREMENT`。
差异确认后写成 `up.sql`，反向操作为 `down.sql`。

## 回滚（rollback）

MySQL 的 DDL 多数隐式提交，**不能像事务一样回滚**，所以回滚能力来自执行前的备份 + 成对的 down 脚本：

```bash
# 执行 DDL 前，先留结构备份
mysql ... -e "CREATE TABLE \`<表>_bak_$(date +%Y%m%d)\` LIKE \`<表>\`;"

# 大表/危险变更（删列、改类型、删表）再补一份数据备份
mysqldump --single-transaction --hex-blob ... <库> <表> | gzip > db/backups/<表>_$(date +%Y%m%d_%H%M%S).sql.gz
```

- rollback = 执行 `down.sql`，必要时从备份恢复表，再刷新 baseline。
- 大表 DDL 尽量在线执行：`ALTER TABLE ... ALGORITHM=INPLACE, LOCK=NONE`。
- 备份文件上传 MinIO / 对象存储并保留一定周期，仓库内只留清单不存数据。

## MySQL 数据备份 / 恢复

```bash
# 全库
mysqldump --single-transaction --routines --triggers --hex-blob --set-gtid-purged=OFF \
  -h "$MYSQL_URL" -P "$MYSQL_PORT" -u "$MYSQL_ROOT_USER" -p"$MYSQL_ROOT_PASSWORD" "$MYSQL_DATABASE" \
  | gzip > db/backups/mydb_$(date +%Y%m%d_%H%M%S).sql.gz

# 恢复
zcat db/backups/mydb_xxx.sql.gz | mysql -h "$MYSQL_URL" ... "$MYSQL_DATABASE"
```

恢复后校验：每张有数据表 `SELECT * FROM <table> LIMIT 1` + 抽样行数对拍；
大表（history / technical_factor / stock_business_breakdown 等百万级表）恢复耗时与磁盘要提前评估。

## Qdrant（规划中，先不处理）

后续做向量库迁移/备份时，沿用同一套原则，文档在 `db/qdrant.md` 补充，要点先记录：

- 每类 collection 的“schema”留档：向量维度、距离度量、payload 字段、创建参数、
  对应 MySQL 元数据表名（`QDRANT_NEWS_COLLECTION` / `QDRANT_PROFILE_COLLECTION` /
  `QDRANT_BUSINESS_BREAKDOWN_COLLECTION` 等）。
- 迁移 = 目标库建同名参数 collection → snapshot 恢复 → 校验点位数；
  rollback = 切回旧 collection 名或从旧 snapshot 恢复。
- 备份 = Qdrant snapshot API（`POST /collections/<name>/snapshots`），snapshot 文件在
  `qdrant_data` volume 内，按周期复制到对象存储。
- docker-compose 里 `qdrant` 服务已挂载 `qdrant_data` volume，恢复时注意与线上版本兼容。

## 操作纪律

- 生产库 DDL 一律走 migration 脚本 + 双人 review，禁止手敲后不留记录。
- up/down 必须成对；只改一个表时也写清影响。
- baseline 变更要随代码一起提交，保持“db/baseline = 线上真实结构”的约定。
- 备份文件不进 git；需要长期保留时放对象存储。

## 可选工具（需要时再加）

若 MySQL 表很多、变更频繁，可考虑补一个轻量 CLI（只留 baseline/diff 两个命令，不保留整套工程），
或引入现成 schema diff 工具；届时同步更新本指南中的命令。
