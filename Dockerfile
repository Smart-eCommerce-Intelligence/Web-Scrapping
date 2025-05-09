FROM python:3.11

WORKDIR /app

COPY Scrapping_Shop.py .
COPY requirements.txt .
COPY stores.json .

RUN pip install --no-cache-dir -r ./requirements.txt
# Assuming mysql-connector-python is in requirements.txt now

ENV DB_HOST_DEFAULT="host.docker.internal"
ENV DB_USER_DEFAULT="root"
ENV DB_PASSWORD_DEFAULT=""
ENV DB_NAME_DEFAULT="scrap_db"
ENV STORES_FILE_PATH_DEFAULT="stores.json"

# Use shell form of CMD to allow environment variable expansion.
# The actual values will come from docker-compose environment or these defaults.
CMD python ./Scrapping_Shop.py \
    --db_host "${DB_HOST:-$DB_HOST_DEFAULT}" \
    --db_user "${DB_USER:-$DB_USER_DEFAULT}" \
    --db_password "${DB_PASSWORD:-$DB_PASSWORD_DEFAULT}" \
    --db_name "${DB_NAME:-$DB_NAME_DEFAULT}" \
    --stores_file_path "${STORES_FILE_PATH_IN_CONTAINER:-$STORES_FILE_PATH_DEFAULT}"