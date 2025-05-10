FROM python:3.11 

WORKDIR /app

# 1. Copy requirements.txt first and install dependencies.
# This layer will be cached as long as requirements.txt doesn't change.
COPY requirements.txt .
RUN pip install --no-cache-dir -r ./requirements.txt

# 2. Copy the rest of your application files.
# If only these change, the pip install layer above will be reused.
COPY Scrapping_Shop.py .
COPY stores.json .

# Environment Variables for defaults (can be overridden at runtime)
ENV DB_HOST_DEFAULT="host.docker.internal"
ENV DB_USER_DEFAULT="root"
ENV DB_PASSWORD_DEFAULT=""
ENV DB_NAME_DEFAULT="scrap_db"
ENV STORES_FILE_PATH_DEFAULT="stores.json"

# Use shell form of CMD to allow environment variable expansion.
CMD python ./Scrapping_Shop.py \
    --db_host "${DB_HOST:-$DB_HOST_DEFAULT}" \
    --db_user "${DB_USER:-$DB_USER_DEFAULT}" \
    --db_password "${DB_PASSWORD:-$DB_PASSWORD_DEFAULT}" \
    --db_name "${DB_NAME:-$DB_NAME_DEFAULT}" \
    --stores_file_path "${STORES_FILE_PATH_IN_CONTAINER:-$STORES_FILE_PATH_DEFAULT}"


