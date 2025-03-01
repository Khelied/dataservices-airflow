import pathlib
from typing import Final

from airflow import DAG
from airflow.operators.python_operator import BranchPythonOperator, PythonOperator
from postgres_on_azure_operator import PostgresOnAzureOperator
from common import SHARED_DIR, MessageOperator, vsd_default_args
from common.sql import SQL_CHECK_COUNT, SQL_CHECK_GEO
from contact_point.callbacks import get_contact_point_on_failure_callback
from importscripts.oplaadpalen.import_oplaadpalen_allego import import_oplaadpalen
from postgres_check_operator import PostgresCheckOperator
from postgres_permissions_operator import PostgresPermissionsOperator
from postgres_xcom_operator import PostgresXcomOperator

SQL_EXISTS_CHECK: Final = """
    SELECT 1 WHERE EXISTS (
       SELECT
       FROM   information_schema.tables
       WHERE  table_schema = 'public'
       AND    table_name = 'oplaadpalen'
       )
"""

SQL_TABLE_RENAME: Final = """
    ALTER TABLE IF EXISTS oplaadpalen RENAME TO oplaadpalen_old;
    ALTER TABLE oplaadpalen_new RENAME TO oplaadpalen;
    CREATE OR REPLACE VIEW oplaadpunten AS SELECT op.*,
        concat_ws(' ', op.provider, '-', op.street, op.housenumber) as name
    FROM oplaadpalen op
        WHERE op.connector_type <> 'SHUNK_PANTOGRAPH' AND op.status not in ('Deleted');
    DROP TABLE IF EXISTS oplaadpalen_old;
"""

dag_id = "oplaadpalen"
sql_path = pathlib.Path(__file__).resolve().parents[0] / "sql"


def choose_branch(**kwargs):
    ti = kwargs["ti"]
    oplaadpalen_exists = ti.xcom_pull(task_ids="check_table_exists") is not None
    return "update_oplaadpalen" if oplaadpalen_exists else "create_oplaadpalen"


with DAG(
    dag_id,
    default_args=vsd_default_args,
    template_searchpath=["/"],
    schedule_interval="@hourly",
    on_failure_callback=get_contact_point_on_failure_callback(dataset_id=dag_id),
) as dag:

    tmp_dir = f"{SHARED_DIR}/{dag_id}"

    # 1. Post info message on slack
    slack_at_start = MessageOperator(
        task_id="slack_at_start",
    )

    check_table_exists = PostgresXcomOperator(
        task_id="check_table_exists", sql=SQL_EXISTS_CHECK, do_xcom_push=True
    )

    branch_task = BranchPythonOperator(task_id="branch_task", python_callable=choose_branch)

    update_oplaadpalen = PostgresOnAzureOperator(
        task_id="update_oplaadpalen",
        sql=f"{sql_path}/oplaadpalen_copy.sql"
    )

    create_oplaadpalen = PostgresOnAzureOperator(
        task_id="create_oplaadpalen",
        sql=f"{sql_path}/oplaadpalen_create.sql"
    )

    # The trigger_rule is essential, otherwise the skipped path blocks progress
    import_allego = PythonOperator(
        task_id="import_allego",
        python_callable=import_oplaadpalen,
        trigger_rule="none_failed_or_skipped",
        provide_context=True,
    )

    check_count = PostgresCheckOperator(
        task_id="check_count",
        sql=SQL_CHECK_COUNT,
        params=dict(tablename=f"{dag_id}_new", mincount=10),
    )

    check_geo = PostgresCheckOperator(
        task_id="check_geo",
        sql=SQL_CHECK_GEO,
        params=dict(tablename=f"{dag_id}_new", geotype="ST_Point"),
    )

    # 10. Grant database permissions
    grant_db_permissions = PostgresPermissionsOperator(task_id="grants", dag_name=dag_id)

    rename_table = PostgresOnAzureOperator(
        task_id="rename_table",
        sql=SQL_TABLE_RENAME,
    )

slack_at_start >> check_table_exists >> branch_task
branch_task >> update_oplaadpalen >> import_allego
branch_task >> create_oplaadpalen >> import_allego
import_allego >> [check_count, check_geo] >> rename_table >> grant_db_permissions
