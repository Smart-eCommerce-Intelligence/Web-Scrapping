# Dockerfile_Woo
FROM python:3.11
WORKDIR /app
COPY requirements.txt . 

RUN pip install --no-cache-dir -r ./requirements.txt

COPY Scrapping_Woo.py .
COPY woo_stores.json . 

ENV DB_HOST_DEFAULT="host.docker.internal"
ENV DB_NAME_DEFAULT="web_scrapdb"
ENV DB_PASSWORD_DEFAULT=""
ENV DB_USER_DEFAULT="root"

ENV CATEGORIES_FILE_DEFAULT="woo_stores.json"

CMD python ./Scrapping_Woo.py \
    --db_host "${DB_HOST:-$DB_HOST_DEFAULT}" \
    --db_name  "${DB_NAME:-$DB_NAME_DEFAULT}" \
    --db_password  "${DB_PASSWORD:-$DB_PASSWORD_DEFAULT}" \
    --db_user  "${DB_USER:-$DB_USER_DEFAULT}" \
    --categories_file_path "${CATEGORIES_FILE:-$CATEGORIES_FILE_DEFAULT}"