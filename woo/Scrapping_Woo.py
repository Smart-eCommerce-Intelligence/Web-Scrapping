from requests_html import HTMLSession
import time
import mysql.connector
from urllib.parse import urljoin
import argparse
import json
from flask import Flask, jsonify, request # Import Flask
import threading # For background tasks
import os # For environment variables like FLASK_PORT

# --- Default Configurations ---
DEFAULT_DB_CONFIG_DEFAULTS = { # Renamed for clarity
    'host': 'localhost',
    'user': 'root',
    'password': '',
    'database': 'scrap_test'
}
DEFAULT_CATEGORIES_FILE = "woo_stores.json"
DEFAULT_CATEGORIES_CONTENT = [
    {'name': 'Version 1', 'url': 'https://barefootbuttons.com/product-category/version-1/'},
    {'name': 'Version 2', 'url': 'https://barefootbuttons.com/product-category/version-2/'},
    {'name': 'Mini', 'url': 'https://barefootbuttons.com/product-category/mini/'},
    {'name': 'Tallboy', 'url': 'https://barefootbuttons.com/product-category/tallboy/'}
]

# --- Argument Parsing ---
parser = argparse.ArgumentParser(description="Scrape product data from Barefoot Buttons categories (WooCommerce).")
parser.add_argument("--db_host", type=str, default=DEFAULT_DB_CONFIG_DEFAULTS['host'], help="Database host")
parser.add_argument("--db_user", type=str, default=DEFAULT_DB_CONFIG_DEFAULTS['user'], help="Database user")
parser.add_argument("--db_password", type=str, default=DEFAULT_DB_CONFIG_DEFAULTS['password'], help="Database password")
parser.add_argument("--db_name", type=str, default=DEFAULT_DB_CONFIG_DEFAULTS['database'], help="Database name")
parser.add_argument("--categories_file_path", type=str, default=DEFAULT_CATEGORIES_FILE, help="Path to categories JSON file")

# Global variable to store parsed arguments from container startup
script_args = None

# --- Database Connection Function (accepts config) ---
def db_connect(current_db_config):
    if not current_db_config:
        print("Error: db_connect called with no configuration for Woo scraper.")
        return None
    try:
        conn = mysql.connector.connect(**current_db_config)
        print(f"Successfully connected to MySQL database for Woo: {current_db_config.get('database', 'N/A')}")
        return conn
    except mysql.connector.Error as err:
        print(f"Error connecting to MySQL for Woo with config {current_db_config}: {err}")
        return None
    except Exception as e_gen:
        print(f"Unexpected error in db_connect for Woo with config {current_db_config}: {e_gen}")
        return None

# --- Your existing Barefoot specific functions ---
# (create_barefoot_table_if_not_exists, insert_product_data, fetch_page_with_retries,
#  get_product_links_from_category_page, get_all_product_links_for_category, get_product_data)
# These functions will be called by run_woo_scraper_logic.
# Ensure they use passed-in db_connection or config where necessary, or can access
# the config created within run_woo_scraper_logic.
# For simplicity, the db_connect used by these will be the one called inside run_woo_scraper_logic.

# --- Global Session for requests_html (initialized once) ---
# It's better to initialize session and headers once if they are global.
# If run_woo_scraper_logic might be called truly concurrently (unlikely with current threading model for one script),
# you might need thread-local sessions or pass sessions around. For now, global is fine.
html_session = HTMLSession()
REQUEST_HEADERS = { # Renamed from HEADERS to avoid conflict if Flask uses HEADERS
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/98.0.4758.102 Safari/537.36'
}
html_session.headers.update(REQUEST_HEADERS)


def create_barefoot_table_if_not_exists(cursor):
    """Creates the barefoot_products table if it doesn't already exist."""
    try:
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS barefoot_products (
                id INT AUTO_INCREMENT PRIMARY KEY,
                product_url VARCHAR(1024) UNIQUE,
                title VARCHAR(255) NOT NULL,
                price VARCHAR(50),
                tag VARCHAR(255),
                sku VARCHAR(100),
                category VARCHAR(100),
                scraped_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
            );
        """)
        try:
            cursor.execute("ALTER TABLE barefoot_products ADD COLUMN category VARCHAR(100) AFTER sku;")
            # print("Ensured 'category' column exists in 'barefoot_products'.") # Less verbose
        except mysql.connector.Error as alter_err:
            if alter_err.errno == 1060: pass
            else: raise
        print("Table 'barefoot_products' checked/created successfully.")
    except mysql.connector.Error as err:
        print(f"Error with barefoot_products table setup: {err}")

def insert_product_data(db_conn, product_data, product_url, category_name_from_config):
    if not db_conn: return
    cursor = None # Initialize cursor
    try:
        cursor = db_conn.cursor()
        sql = """
        INSERT INTO barefoot_products (product_url, title, price, tag, sku, category)
        VALUES (%s, %s, %s, %s, %s, %s)
        ON DUPLICATE KEY UPDATE
            title = VALUES(title), price = VALUES(price), tag = VALUES(tag),
            sku = VALUES(sku), category = VALUES(category), scraped_at = CURRENT_TIMESTAMP;
        """
        values = (
            product_url, product_data.get('title', 'N/A'), product_data.get('price', 'N/A'),
            product_data.get('tag', 'N/A'), product_data.get('sku', 'N/A'), category_name_from_config
        )
        cursor.execute(sql, values)
    except mysql.connector.Error as err:
        print(f"DB Error for {product_url} (Woo): {err}")
    finally:
        if cursor: cursor.close()


def fetch_page_with_retries(url, retries=3, delay=5, timeout=25):
    global html_session # Use the global session
    for i in range(retries):
        try:
            r = html_session.get(url, timeout=timeout)
            r.raise_for_status()
            return r
        except Exception as e:
            print(f"Error fetching {url} (Attempt {i+1}/{retries}): {e}")
            if i < retries - 1: time.sleep(delay)
            else: return None

def get_product_links_from_category_page(page_url):
    # ... (Your existing logic for this function) ...
    # Ensure it uses the global html_session or takes session as an argument
    print(f"Fetching product links from: {page_url}")
    r = fetch_page_with_retries(page_url) # Uses global html_session via fetch_page_with_retries
    if not r or not r.html:
        print(f"Failed to fetch/parse HTML for {page_url}")
        return [], None

    product_item_selector = 'div.product-small.box'
    items = r.html.find(product_item_selector)
    links = []
    if not items: print(f"No product items found on {page_url} with selector '{product_item_selector}'.")

    for item in items:
        link_tag = item.find('a.woocommerce-LoopProduct-link', first=True) or \
                   item.find('p.name.product-title > a', first=True) or \
                   item.find('a', first=True)
        if link_tag and 'href' in link_tag.attrs:
            links.append(urljoin(page_url, link_tag.attrs['href']))
        else:
            print(f"Warning: Product item on {page_url} missing valid link.")

    next_page_selector = 'a.next.page-numbers'
    next_page_tag = r.html.find(next_page_selector, first=True)
    next_page_url = urljoin(page_url, next_page_tag.attrs['href']) if next_page_tag and 'href' in next_page_tag.attrs else None
    if next_page_url: print(f"Found next page: {next_page_url}")
    else: print(f"No 'Next Page' link found on {page_url}.")
    return links, next_page_url


def get_all_product_links_for_category(start_category_url):
    # ... (Your existing logic for this function) ...
    all_links_for_category = []
    current_page_url = start_category_url
    max_pages, pages_scraped = 20, 0
    while current_page_url and pages_scraped < max_pages:
        pages_scraped += 1
        print(f"\n--- Scraping links from page {pages_scraped} of Woo category: {current_page_url} ---")
        links_on_page, next_page_url_candidate = get_product_links_from_category_page(current_page_url)
        newly_added = 0
        for link in links_on_page:
            if link not in all_links_for_category:
                all_links_for_category.append(link)
                newly_added += 1
        print(f"Collected {newly_added} new links. Total unique for category: {len(all_links_for_category)}")
        if not links_on_page and newly_added == 0: print(f"No links found or added from {current_page_url}.")

        if next_page_url_candidate and next_page_url_candidate != current_page_url:
            current_page_url = next_page_url_candidate
            time.sleep(1.5)
        else:
            if next_page_url_candidate == current_page_url and next_page_url_candidate is not None:
                 print(f"Warning: Woo Next page URL is same as current. Stopping pagination.")
            current_page_url = None
    if pages_scraped == max_pages and current_page_url: print(f"Warning: Reached max_pages for {start_category_url}.")
    return all_links_for_category


def get_product_data(product_url):
    # ... (Your existing logic for this function) ...
    # Ensure it uses the global html_session or takes session as an argument
    print(f"Scraping Woo product data from: {product_url}")
    r = fetch_page_with_retries(product_url) # Uses global html_session
    if not r or not r.html: return None
    product_details = {}
    try:
        title_el = r.html.find('h1.product_title.entry-title', first=True)
        product_details['title'] = title_el.full_text.strip() if title_el else 'N/A'
        price_elements = r.html.find('span.woocommerce-Price-amount.amount bdi')
        if len(price_elements) > 1: product_details['price'] = price_elements[1].full_text.strip()
        elif price_elements: product_details['price'] = price_elements[0].full_text.strip()
        else:
            price_any = r.html.find('p.price span.woocommerce-Price-amount.amount', first=True)
            product_details['price'] = price_any.text.strip() if price_any else 'N/A'
        tag_el = r.html.find('span.tagged_as a[rel=tag]', first=True)
        product_details['tag'] = tag_el.full_text.strip() if tag_el else 'N/A'
        sku_el = r.html.find('span.sku', first=True)
        product_details['sku'] = sku_el.full_text.strip() if sku_el else 'N/A'
        print(f"Scraped Woo: {product_details}")
        return product_details
    except Exception as e:
        print(f"Error parsing Woo product data for {product_url}: {e}")
        return {k: 'N/A (Parse Error)' for k in ['title', 'price', 'tag', 'sku']}

# --- Main WooCommerce Scraping Logic ---
def run_woo_scraper_logic(cmd_args):
    print(f"WooCommerce scraper logic triggered with args: {cmd_args}")
    current_run_db_config = {
        'host': cmd_args.db_host, 'user': cmd_args.db_user,
        'password': cmd_args.db_password, 'database': cmd_args.db_name
    }
    print(f"DEBUG (Woo scraper logic): current_run_db_config set to: {current_run_db_config}")

    BAREFOOT_CATEGORIES_TO_SCRAPE = [] # Initialize
    try:
        print(f"DEBUG (Woo scraper logic): Attempting to load categories from: {cmd_args.categories_file_path}")
        with open(cmd_args.categories_file_path, 'r') as f:
            categories_data = json.load(f)
        if isinstance(categories_data, list) and all(isinstance(c, dict) and 'name' in c and 'url' in c for c in categories_data):
            BAREFOOT_CATEGORIES_TO_SCRAPE = categories_data
            print(f"DEBUG (Woo scraper logic): Categories loaded: {len(BAREFOOT_CATEGORIES_TO_SCRAPE)}")
        else:
            print(f"Error (Woo scraper logic): Invalid categories file format. Using fallback.")
            BAREFOOT_CATEGORIES_TO_SCRAPE = DEFAULT_CATEGORIES_CONTENT
    except Exception as e:
        print(f"Error (Woo scraper logic): Loading categories file '{cmd_args.categories_file_path}': {e}. Using fallback.")
        BAREFOOT_CATEGORIES_TO_SCRAPE = DEFAULT_CATEGORIES_CONTENT

    if not BAREFOOT_CATEGORIES_TO_SCRAPE:
        print("Critical (Woo scraper logic): No categories to process.")
        return {"status": "error", "message": "No categories configured."}

    db_connection = db_connect(current_run_db_config)
    if not db_connection:
        print("Could not connect to database for Woo scraper.")
        return {"status": "error", "message": "DB connection failed."}

    cursor = db_connection.cursor()
    create_barefoot_table_if_not_exists(cursor)
    
    try:
        delete_query = "DELETE FROM barefoot_products" # Deletes all rows
        # You could also use TRUNCATE TABLE barefoot_products for potentially faster deletion
        # delete_query = "TRUNCATE TABLE barefoot_products"
        
        cursor.execute(delete_query)
        deleted_rows_count = cursor.rowcount
        db_connection.commit() # Commit the delete operation
        print(f"(Woo Scraper Logic) DELETED {deleted_rows_count} existing product entries from the 'barefoot_products' table.")
    except mysql.connector.Error as err:
        print(f"Error deleting all data from 'barefoot_products' table: {err}")
        # CRITICAL: Decide if you want to stop if deletion fails.
        if cursor: cursor.close()
        if db_connection and db_connection.is_connected(): db_connection.close()
        return {"status": "error", "message": f"Failed to clear barefoot_products table: {err}"}
    except Exception as e_del:
        print(f"Unexpected error during data deletion: {e_del}")
        if cursor: cursor.close()
        if db_connection and db_connection.is_connected(): db_connection.close()
        return {"status": "error", "message": f"Unexpected error clearing barefoot_products table: {e_del}"}
    # --- End of NEW deletion logic ---
    
    
    cursor.close() # Close cursor after table creation, new ones will be opened by insert_product_data

    total_products_processed_for_db = 0
    for category_config in BAREFOOT_CATEGORIES_TO_SCRAPE:
        category_name_for_db = category_config['name']
        category_start_url = category_config['url']
        print(f"\n{'='*20} Processing Woo Category: {category_name_for_db} ({category_start_url}) {'='*20}")

        product_page_links = get_all_product_links_for_category(category_start_url)
        if not product_page_links:
            print(f"No product links for Woo category '{category_name_for_db}'. Skipping.")
            continue

        print(f"\nFound {len(product_page_links)} total product links for Woo '{category_name_for_db}'. Extracting data...")
        products_in_this_category_db = 0
        for i, link in enumerate(product_page_links):
            print(f"Processing Woo product {i+1}/{len(product_page_links)}...")
            product_info = get_product_data(link)
            if product_info:
                insert_product_data(db_connection, product_info, link, category_name_for_db)
                products_in_this_category_db +=1
            time.sleep(1) # Respectful delay

        db_connection.commit() # Commit after each category
        print(f"Woo Category '{category_name_for_db}' completed. {products_in_this_category_db} products processed.")
        total_products_processed_for_db += products_in_this_category_db
        time.sleep(3)

    if db_connection and db_connection.is_connected(): db_connection.close()
    print(f"\nDone scraping all Woo categories. Total products processed: {total_products_processed_for_db}")
    return {"status": "success", "message": f"WooCommerce scraping finished. Products processed: {total_products_processed_for_db}"}
# --- End of Main WooCommerce Scraping Logic ---


# --- Flask App Setup ---
app = Flask(__name__)
is_scraping_woo = False
scraper_thread_woo = None

@app.route('/run_woo_scrape', methods=['POST'])
def trigger_woo_scrape():
    global is_scraping_woo, scraper_thread_woo, script_args # Access global script_args

    if script_args is None:
        return jsonify({"status": "error", "message": "Woo script arguments not initialized."}), 500

    if is_scraping_woo and scraper_thread_woo and scraper_thread_woo.is_alive():
        return jsonify({"status": "busy", "message": "WooCommerce scraping is already in progress."}), 429

    print("API: Received request to run WooCommerce scraper.")
    is_scraping_woo = True
    scraper_thread_woo = threading.Thread(target=run_scraper_with_status_update_woo, args=(script_args,))
    scraper_thread_woo.start()
    return jsonify({"status": "triggered", "message": "WooCommerce scraping process started in background."}), 202

def run_scraper_with_status_update_woo(current_script_args_for_thread):
    global is_scraping_woo
    try:
        run_woo_scraper_logic(current_script_args_for_thread)
    except Exception as e:
        print(f"Exception during WooCommerce scraper execution thread: {e}")
    finally:
        is_scraping_woo = False
        print("WooCommerce scraper thread finished.")

if __name__ == '__main__':
    script_args = parser.parse_args() # Parse args ONCE when the script starts
    print(f"Initial Barefoot (Woo) scraper arguments parsed: {script_args}")

    port = int(os.environ.get("FLASK_PORT_WOO", 5002)) # Use a different port/env var
    print(f"Starting WooCommerce (Barefoot) Scraper Flask API on port {port}")
    app.run(host='0.0.0.0', port=port, debug=False)