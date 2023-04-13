from pyspark.sql import SparkSession

spark = SparkSession.builder \
    .master("local[*]") \
    .appName("hive_to_iceberg") \
    .config("spark.sql.warehouse.dir", './hive-warehouse') \
    .config('spark.sql.catalog.spark_catalog', 'org.apache.iceberg.spark.SparkSessionCatalog') \
    .config('spark.sql.catalog.spark_catalog.type', 'hive') \
    .enableHiveSupport()
# .config('spark.sql.catalog.spark_catalog.uri', 'thrift://127.0.0.1:9083') \
# .config("hive.metastore.uris", 'thrift://127.0.0.1:9083')

# iceberg catalog
spark = spark \
    .config('spark.sql.catalog.iceberg', 'org.apache.iceberg.spark.SparkCatalog') \
    .config('spark.sql.catalog.iceberg.type', 'hadoop') \
    .config('spark.sql.catalog.iceberg.warehouse', './iceberg-warehouse') \
    .config('spark.sql.extensions', 'org.apache.iceberg.spark.extensions.IcebergSparkSessionExtensions') \
    .getOrCreate()


def write_hive_orc_table():
    spark.read.format("json").load("./data/flight-data/json").createOrReplaceTempView("summary")
    spark.sql("SET hive.exec.dynamic.partition.mode=non-strict;")
    sql = f"""
    create table flight
    partitioned by (dest_country_name)
    stored as ORC
    TBLPROPERTIES ("transactional" = "false")
    as select * from summary
    """
    spark.sql(sql)


def write_iceberg_table(table_name):
    sql = f"""insert overwrite {table_name} select * from flight"""
    spark.sql(sql)


"""
reference: 
https://www.dremio.com/blog/migrating-a-hive-table-to-an-iceberg-table-hands-on-tutorial/
https://iceberg.apache.org/docs/latest/spark-procedures/#table-migration
"""
if __name__ == '__main__':
    spark.sql("show tables").show()

    # 1. prepare hive table
    write_hive_orc_table()

    # 2. An in-place migration means we will leave the existing data files as-is and create only the metadata for the
    # new Iceberg table using the data files of the existing Hive table.

    # snapshot:
    spark.sql("CALL iceberg.system.snapshot(table => 'iceberg.db.flight_snapshot', source_table => 'default.flight')")
    # new files are placed in the snapshot table’s location rather than the original table location.
    # write_iceberg_table('iceberg.db.flight_snapshot')
    # drop table only remove iceberg table files

    # migrate:
    # spark.sql("CALL iceberg.system.migrate(table => 'flight')").show()

    # add_files:
    # spark.sql("CALL iceberg.system.add_files(table => 'iceberg.db.flight', source_table => 'flight')")
    # This procedure will not analyze the schema of the files to determine if they actually match the
    # schema of the Iceberg table.
    # drop table will also remove hive table files

    # 3. iceberg-shell test
    # select * from iceberg.db.flight_snapshot limit 10;
    # select file_path from iceberg.db.flight_snapshot.files limit 10;
    # select snapshot_id, manifest_list from iceberg.db.flight_snapshot.snapshots;
