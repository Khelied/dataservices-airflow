import re
import subprocess
from typing import Any, Dict, Optional

from airflow.models.baseoperator import BaseOperator
from airflow.utils.decorators import apply_defaults
from environs import Env


class PgComparatorCDCOperator(BaseOperator):
    """Efficiently populate target table with changes from source table.

    PG_comparator CDC (change data capture) is used to detect modifications (inserts,
    updates and deletes) in a source table when compared to a target table, that presents the
    previous state, but should be updated to the new state. When it has found the modifications
    it will apply them to the target table.

    This is a much more efficient process than copying over the entire source table to the
    target table. Especially when the source table has many rows and the changes are few.

    To speed up the process even more one should enable the ``use_pg_copy`` option.

    .. note:: The ``use_pg_copy`` option requires the presence of an integer primary key. It is
       possible to specify an alternate key (see ``key_column`` parameter), but that one too
       needs to be of an integer type. The largest supported integer type is PostgreSQL's
       ``BIGINT``. Although PostgreSQL can store much larger numerical values using its
       ``NUMERIC`` type, that type is not supported by ``pg_comparator``.

    If the primary key or alternate key has an integer type, consider using the ``use_key`` option;
    it will stop ``pg_comparator`` from needlessly hashing the key and *use the key* as-is.
    """

    @apply_defaults  # type: ignore [misc]
    def __init__(
        self,
        source_table: str,
        target_table: str,
        use_pg_copy: bool = False,
        key_column: Optional[str] = None,
        use_key: bool = False,
        db_conn_id: Optional[str] = None,
        *args: Any,
        **kwargs: Any,
    ):
        """Initialize PgComparatorCDCOperator.

        Args:
            source_table: Table to take changes from.
            target_table: Table to update with changes from ``source_table`.
            use_pg_copy: Whether to use experimental, but much faster ``--pg-copy`` option.
                Requires a integer primary or numeric alternate key
            key_column: If specified, tells ``pg_comparator`` to not use the primary key, but
                use an alternate key for identifying rows.
            use_key: Don't calculate a hash of the the primary key or alternate key, but use it
                as-is (because it already is an integer)
            db_conn_id: Database URL (hence, not an Airflow connection_id, why?)
            *args:
            **kwargs:
        """
        super().__init__(*args, **kwargs)
        self.source_table = source_table
        self.target_table = target_table
        self.use_pg_copy = use_pg_copy
        self.key_column = key_column
        self.use_key = use_key
        self.db_conn_id = db_conn_id if db_conn_id else "AIRFLOW_CONN_POSTGRES_DEFAULT"

    def execute(self, context: Dict[str, Any]) -> None:
        env = Env()
        db_connection, _ = env(self.db_conn_id).split("?")
        db_url = re.sub(r".*?(?=://)", "pgsql", db_connection, count=1)

        source_url = f"{db_url}/{self.source_table}"
        if self.key_column is not None:
            # `pg_comparator` expects an alternate key to be passed in as part of the DB URL and
            # not as a separate command line argument. The alternate key is specified as the
            # first query parameter and has no value.
            source_url += f"?{self.key_column}"
        target_url = f"{db_url}/{self.target_table}"

        self.log.info(
            "Start change data capture (with pg_comparator) from: '%s' to: '%s" ".",
            source_url,
            target_url,
        )
        arguments = [
            "/usr/bin/pg_comparator",
            "--do-it",
            "--synchronize",
            "--max-ratio=2.0",
            f"--prefix={self.target_table}_cmp",
        ]
        if self.use_pg_copy:
            arguments.extend(["--pg-copy=128", "--no-async"])
        if self.use_key:
            arguments.append("--use-key")
        arguments.extend([source_url, target_url])
        self.log.info("Executing: '%s'.", " ".join(arguments))
        result = subprocess.run(
            arguments,
            capture_output=True,
            check=True,
        )
        self.log.debug(result.stdout)
