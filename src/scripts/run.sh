#!/bin/bash
export AIRFLOW__CORE__SQL_ALCHEMY_CONN=${AIRFLOW__CORE__SQL_ALCHEMY_CONN:-`echo $AIRFLOW_CONN_POSTGRES_DEFAULT | cut -d'?' -f 1`}
export AIRFLOW_CONN_POSTGRES_VSD={$AIRFLOW_CONN_POSTGRES_VSD:-$AIRFLOW__CORE__SQL_ALCHEMY_CONN}
airflow initdb  # initdb is not destructive, so can be re-run at startup
python scripts/mkvars.py
# Airflow does not support slack connection config through environment var
# So we (re-)create the slack connection on startup.
airflow connections --delete --conn_id slack
airflow connections --add  --conn_id slack --conn_host $SLACK_WEBHOOK_HOST \
    --conn_password "/$SLACK_WEBHOOK" --conn_type http

airflow connections --delete --conn_id geozet_conn_id
airflow connections --add  --conn_id geozet_conn_id --conn_host http://geozet.koop.overheid.nl \
    --conn_type http

airflow connections --delete --conn_id hior_conn_id
airflow connections --add  --conn_id hior_conn_id \
    --conn_host http://131f4363709c46b89a6ba5bc764b38b9.objectstore.eu \
    --conn_type http

airflow connections --delete --conn_id ams_maps_conn_id
airflow connections --add  --conn_id ams_maps_conn_id \
    --conn_host https://maps.amsterdam.nl \
    --conn_type http

airflow connections --delete --conn_id fietspaaltjes_conn_id
airflow connections --add  --conn_id fietspaaltjes_conn_id \
    --conn_host https://cdn.endora.nl \
    --conn_type http

airflow connections --delete --conn_id api_data_amsterdam_conn_id
airflow connections --add  --conn_id api_data_amsterdam_conn_id \
    --conn_host  https://api.data.amsterdam.nl  \
    --conn_type http
    
airflow connections --delete --conn_id schemas_data_amsterdam_conn_id
airflow connections --add  --conn_id schemas_data_amsterdam_conn_id \
    --conn_host  https://schemas.data.amsterdam.nl \
    --conn_type http

airflow connections --delete --conn_id airflow_home_conn_id
airflow connections --add  --conn_id airflow_home_conn_id \
    --conn_host  /usr/local/airflow/ \
    --conn_type http

airflow connections --delete --conn_id verlichting_conn_id
airflow connections --add  --conn_id verlichting_conn_id \
    --conn_host https://asd2.techtek.eu \
    --conn_type http

# airflow variables -i vars/vars.json &
# airflow scheduler &
# airflow webserver
airflow variables -i vars/vars.json
/usr/local/bin/supervisord --config /usr/local/airflow/etc/supervisord.conf
