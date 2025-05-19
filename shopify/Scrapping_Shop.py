
import requests
import mysql.connector
import time
import argparse
import json
from flask import Flask, jsonify, request
import threading
import os

# --- Default Configurations ---
DEFAULT_STORES_FILE = "stores.json"
DEFAULT_STORES_LIST_CONTENT = [ # Fallback content if file is bad or for testing
    "https://www.allbirds.com",
    "https://www.brooklinen.com",
    "https://www.untuckit.com",
    "https://tattly.com",
    "https://flowrette.com"
]
DEFAULT_DB_CONFIG_DEFAULTS = { # Renamed to avoid confusion with the instance
    'host': 'localhost',
    'user': 'root',
    'password': '',
    'database': 'scrap_test'
}

# --- Argument Parsing ---
parser = argparse.ArgumentParser(description="Scrape product data from Shopify stores.")
parser.add_argument("--db_host", type=str, default=DEFAULT_DB_CONFIG_DEFAULTS['host'], help="...")
parser.add_argument("--db_user", type=str, default=DEFAULT_DB_CONFIG_DEFAULTS['user'], help="...")
parser.add_argument("--db_password", type=str, default=DEFAULT_DB_CONFIG_DEFAULTS['password'], help="...")
parser.add_argument("--db_name", type=str, default=DEFAULT_DB_CONFIG_DEFAULTS['database'], help="...")
parser.add_argument("--stores_file_path", type=str, default=DEFAULT_STORES_FILE, help="...")

# This will be the single source of truth for startup configuration
script_args = None # Will be populated in __main__

# --- Database Connection Function (Modified) ---
def db_connect(current_db_config): # <<<< NOW ACCEPTS current_db_config
    """Establishes a connection to the MySQL database using the provided config."""
    if not current_db_config:
        print("Error: db_connect called with no configuration.")
        return None
    try:
        # print(f"DEBUG db_connect: Connecting with {current_db_config}") # Optional debug
        conn = mysql.connector.connect(**current_db_config)
        print(f"Successfully connected to MySQL database: {current_db_config.get('database', 'N/A')}")
        return conn
    except mysql.connector.Error as err:
        print(f"Error connecting to MySQL with config {current_db_config}: {err}")
        return None
    except Exception as e_gen:
        print(f"Unexpected error in db_connect with config {current_db_config}: {e_gen}")
        return None


def create_table_if_not_exists(cursor):
    # ... (your existing table creation logic) ...
    try:
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS products (
                id INT AUTO_INCREMENT PRIMARY KEY,
                product_url VARCHAR(1024) UNIQUE,
                title VARCHAR(512) NOT NULL,
                vendor VARCHAR(255),
                price DECIMAL(10, 2),
                availability VARCHAR(50),
                description TEXT,
                category VARCHAR(255),
                store_name VARCHAR(100),
                scraped_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
            );
        """)
        print("Table 'products' checked/created successfully.")
    except mysql.connector.Error as err:
        print(f"Error creating table: {err}")

# --- Main Scraping Logic (refactored from your original main) ---
def run_shopify_scraper_logic(cmd_args): # cmd_args comes from the global script_args
    # ... (DB_CONFIG setup, stores loading, REQUEST_HEADERS, db_connection, cursor, create_table as before) ...
    print(f"Shopify scraper logic triggered with args: {cmd_args}")
    current_run_db_config = {
        'host': cmd_args.db_host, 'user': cmd_args.db_user,
        'password': cmd_args.db_password, 'database': cmd_args.db_name
    }
    print(f"DEBUG (scraper logic): current_run_db_config set to: {current_run_db_config}")

    stores = [] # Initialize
    # ... (stores loading logic as you have it) ...
    try:
        print(f"DEBUG (scraper logic): Attempting to load stores from file: {cmd_args.stores_file_path}")
        with open(cmd_args.stores_file_path, 'r') as f:
            stores_data_from_file = json.load(f)
        if isinstance(stores_data_from_file, list):
            stores = stores_data_from_file
            print(f"DEBUG (scraper logic): Stores loaded successfully: {stores}")
        else:
            print(f"Error (scraper logic): Content of '{cmd_args.stores_file_path}' is not a valid JSON list. Using fallback.")
            stores = DEFAULT_STORES_LIST_CONTENT
    except Exception as e:
        print(f"Error (scraper logic): Loading stores from '{cmd_args.stores_file_path}': {e}. Using fallback.")
        stores = DEFAULT_STORES_LIST_CONTENT

    if not stores:
        print("Critical (scraper logic): No stores to process. Exiting scraper logic.")
        return {"status": "error", "message": "No stores configured or loaded."}

    REQUEST_HEADERS = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/98.0.4758.102 Safari/537.36'
    }
    db_connection = db_connect(current_run_db_config)
    if not db_connection:
        print("Could not connect to database for Shopify scraper. Exiting scraper logic.")
        return {"status": "error", "message": "Database connection failed."}

    cursor = db_connection.cursor()
    create_table_if_not_exists(cursor)
    total_products_affected = 0

    for base_url in stores:
        store_name_parts = base_url.replace("https://www.", "").replace("https://", "").split('.')
        store_name = store_name_parts[0] if store_name_parts else base_url
        print(f"\n(Scraper Logic) Scraping store: {store_name} from {base_url}")
        page = 1
        products_this_store_count = 0

        while True:
            url = f"{base_url}/products.json?page={page}&limit=250" # Define URL for the current page
            print(f"(Scraper Logic) Fetching: {url}")

            try:
                response = requests.get(url, headers=REQUEST_HEADERS, timeout=30)
                response.raise_for_status()
            except requests.exceptions.HTTPError as http_err:
                status_code = http_err.response.status_code
                if status_code == 404:
                    print(f"Page {page} not found for {store_name} (404), likely end of products for this store.")
                # ... (other HTTPError handling) ...
                else:
                    print(f"HTTP error fetching {url}: {http_err}")
                break # Stop processing this store on HTTP errors
            except requests.exceptions.RequestException as req_err:
                print(f"Request error fetching {url}: {req_err}")
                break # Stop processing this store

            try:
                data = response.json()
            except requests.exceptions.JSONDecodeError:
                print(f"Failed to decode JSON from {url}. Content snippet: {response.text[:200]}")
                break # Stop processing this store

            products_on_page = data.get("products", []) # <<<< ASSIGNMENT OF products_on_page

            if not products_on_page: # Now this check is valid
                if page == 1:
                    print(f"No products found on the first page for {store_name}. The /products.json endpoint might be disabled or empty.")
                else:
                    print(f"No more products found on page {page} for {store_name}.")
                break # End of products for this store

            for product in products_on_page:
                try:
                    # ... (your product extraction and DB insertion logic) ...
                    title = product.get('title', 'N/A')
                    vendor = product.get('vendor', 'N/A')
                    variants = product.get('variants', [])
                    first_variant = variants[0] if variants else {}
                    price_str = first_variant.get('price', '0.0')
                    price = float(price_str) if price_str else 0.0
                    availability = "Available" if first_variant.get('available', False) else "Out of Stock"
                    description = product.get('body_html', '')
                    category = product.get('product_type', 'N/A')
                    handle = product.get('handle')
                    product_link = f"{base_url}/products/{handle}" if handle else 'N/A'

                    values_tuple = (
                        product_link, title, vendor, price, availability,
                        description, category, store_name
                    )
                    # Ensure your SQL query is defined here or accessible
                    sql_query = """
                    INSERT INTO products (product_url, title, vendor, price, availability, description, category, store_name)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                    ON DUPLICATE KEY UPDATE
                        title = VALUES(title), vendor = VALUES(vendor), price = VALUES(price),
                        availability = VALUES(availability), description = VALUES(description),
                        category = VALUES(category), store_name = VALUES(store_name),
                        scraped_at = CURRENT_TIMESTAMP;
                    """
                    cursor.execute(sql_query, values_tuple)
                    total_products_affected += 1
                    products_this_store_count +=1
                except Exception as e_prod:
                    print(f"Error processing product {product.get('title', 'Unknown')}: {e_prod}")

            db_connection.commit()
            print(f"Page {page} for {store_name} (found {len(products_on_page)} products) committed to DB. Total for this store so far: {products_this_store_count}")
            page += 1
            time.sleep(1.5)

        print(f"Finished scraping {store_name}. Total products from this store: {products_this_store_count}")
        time.sleep(3)

    print(f"\nShopify scraper logic finished. Total products affected: {total_products_affected}")
    if cursor: cursor.close()
    if db_connection and db_connection.is_connected(): db_connection.close()
    return {"status": "success", "message": f"Shopify scraping finished. Products affected: {total_products_affected}"}

# --- Flask App Setup ---
# ... (Flask app setup as before, no changes needed here) ...
app = Flask(__name__)
is_scraping_shopify = False
scraper_thread_shopify = None

@app.route('/run_shopify_scrape', methods=['POST'])
def trigger_shopify_scrape():
    global is_scraping_shopify, scraper_thread_shopify, script_args

    if script_args is None: # Should have been set in __main__
        return jsonify({"status": "error", "message": "Script arguments not initialized."}), 500

    if is_scraping_shopify and scraper_thread_shopify and scraper_thread_shopify.is_alive():
        return jsonify({"status": "busy", "message": "Shopify scraping is already in progress."}), 429

    print("API: Received request to run Shopify scraper.")
    is_scraping_shopify = True

    scraper_thread_shopify = threading.Thread(target=run_scraper_with_status_update_shopify, args=(script_args,))
    scraper_thread_shopify.start()

    return jsonify({"status": "triggered", "message": "Shopify scraping process started in background."}), 202

def run_scraper_with_status_update_shopify(current_script_args_for_thread):
    global is_scraping_shopify
    try:
        run_shopify_scraper_logic(current_script_args_for_thread)
    except Exception as e:
        print(f"Exception during Shopify scraper execution thread: {e}") # Log the error
    finally:
        is_scraping_shopify = False
        print("Shopify scraper thread finished.")

if __name__ == '__main__':
    script_args = parser.parse_args()
    print(f"Initial script arguments parsed: {script_args}")

    port = int(os.environ.get("FLASK_PORT", 5001))
    print(f"Starting Shopify Scraper Flask API on port {port}")
    app.run(host='0.0.0.0', port=port, debug=False)