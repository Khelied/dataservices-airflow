# @@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@ #
# NOTE: Only needed for CloudVPS. On Azure each datateam has its own Airflow instance.
#
# To add generic permissions to the defined roles in `run.sh`, the Airflow API can be used.
# Unfortuneatly, this cannot be done by the Aiflow CLI. Alternatively you can add the permissions
# by hand in the Airflow GUI but that cannot be automated.
#
# The specific DAG LEVEL permissions are defined at DAG definition level since some DAG's
# like GOB are generated. Listing all DAG's by hand for read and access roles can be
# therefore quite cumbersome / error prone.
#
# The API can only be called when Airflow is running. This is why we run this as a background
# process (that is allowed to crash without stopping Airflow itself).
# @@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@ #

until $(curl --output /dev/null --silent --head --fail ${AIRFLOW__WEBSERVER__BASE_URL}:${AIRFLOW__WEBSERVER__BASE_URL_PORT}); do
    echo '*** Message from "airlow_high_level_role_perms.sh": Waiting for Airflow to fully start... ***'
    sleep 30
done

echo '@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@'
echo 'Airflow is ***AWAKE***. Setting generic permissions to custom roles.......'
echo '@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@'

users="team_benk team_ruimte dataservices"

for user in ${users[@]}; do \
curl -X PATCH "${AIRFLOW__WEBSERVER__BASE_URL}:${AIRFLOW__WEBSERVER__BASE_URL_PORT}/api/v1/roles/$user" --user admin:${AIRFLOW_USER_ADMIN_PASSWD:-admin} \
-H  "accept: application/json" -H  "Content-Type: application/json" \
-d "{\"actions\":[{\"action\":{\"name\":\"can_read\"},\"resource\":{\"name\":\"Website\"}},\
    {\"action\":{\"name\":\"can_read\"},\"resource\":{\"name\":\"Task Instances\"}},\
    {\"action\":{\"name\":\"can_read\"},\"resource\":{\"name\":\"Task Logs\"}},\
    {\"action\":{\"name\":\"can_read\"},\"resource\":{\"name\":\"DAG Runs\"}},\
    {\"action\":{\"name\":\"can_read\"},\"resource\":{\"name\":\"DAG Code\"}},\
    {\"action\":{\"name\":\"can_create\"},\"resource\":{\"name\":\"DAG Runs\"}}],\"name\":\"$user\"}"; done
