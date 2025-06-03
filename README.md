# E-commerce Product Scrapers (Shopify & WooCommerce)

This repository contains Python scripts designed to scrape product data from e-commerce websites built on Shopify and WooCommerce platforms. The scraped data is then stored in a MySQL database for further analysis.

## Project Overview

The primary goal of these scrapers is to collect detailed product information, including:

*   **Shopify Scraper (`shopify_scraper/`):**
    *   Product Title
    *   Vendor
    *   Price
    *   Availability
    *   Description (HTML)
    *   Product Category/Type
    *   Product URL
    *   Store Name
*   **WooCommerce Scraper (`woo_scraper/`):**
    *   Product Title
    *   Price
    *   Tags
    *   SKU
    *   Product Category (derived from the scraped category page)
    *   Product URL
    *   Store Name (currently hardcoded for "Barefoot Buttons" but can be adapted)

This data serves as the input for a subsequent analysis pipeline that identifies top-performing products based on various metrics.

## Repository Structure

```
.
├── shopify_scraper/
│   ├── Scrapping_Shop.py       # Main script for Shopify scraping
│   ├── stores.json             # Configuration file listing Shopify store URLs
│   ├── Dockerfile              # Dockerfile for containerizing the Shopify scraper
│   └── requirements.txt        # Python dependencies for Shopify scraper
├── woo_scraper/
│   ├── Scrapping_Woo.py        # Main script for WooCommerce (Barefoot Buttons) scraping
│   ├── barefoot_categories.json # Configuration for WooCommerce categories to scrape (e.g., Barefoot Buttons)
│   ├── Dockerfile              # Dockerfile for containerizing the WooCommerce scraper
│   └── requirements.txt        # Python dependencies for WooCommerce scraper
└── README.md                   # This file
```

## Prerequisites

*   Python 3.8+
*   MySQL Server accessible by the scripts
*   Docker (if running via containers)
*   Access to the internet to reach the target e-commerce sites

## Setup and Installation

### 1. Clone the Repository

```bash
git clone https://github.com/Smart-eCommerce-Intelligence/Web-Scrapping
cd Web-Scrapping
```

### 2. Database Setup

Ensure you have a MySQL database server running and accessible. The scripts will attempt to create the necessary tables if they don't exist. You'll need to provide database credentials.

*   **Shopify Scraper:** Expects a database (e.g., `shopify_data`) and will create a `products` table.
*   **WooCommerce Scraper:** Expects a database (e.g., `web_scraping_db`) and will create a `barefoot_products` table.

### 3. Python Environment (if running locally without Docker)

It's recommended to use a virtual environment:

```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

Install dependencies for each scraper:

```bash
pip install -r shopify_scraper/requirements.txt
pip install -r woo_scraper/requirements.txt
```

**`shopify_scraper/requirements.txt` should contain:**

```
requests
mysql-connector-python
# argparse is part of standard library
# json is part of standard library
```

**`woo_scraper/requirements.txt` should contain:**

```
requests-html  # For HTML parsing and JavaScript rendering (if used, though current script is static)
mysql-connector-python
# argparse is part of standard library
# json is part of standard library
```

### 4. Configuration

*   **Shopify Scraper (`shopify_scraper/stores.json`):**
    Update this JSON file with a list of Shopify store base URLs you want to scrape.
    Example:
    ```json
    [
        "https://www.allbirds.com",
        "https://www.untuckit.com"
    ]
    ```

*   **WooCommerce Scraper (`woo_scraper/barefoot_categories.json`):**
    This file is configured to scrape categories from a specific WooCommerce site (Barefoot Buttons by default). Each entry needs a `name` (for the category label in the DB) and a `url` (the category page URL).
    Example:
    ```json
    [
        {
            "name": "Version 1",
            "url": "https://barefootbuttons.com/product-category/version-1/"
        },
        {
            "name": "Version 2",
            "url": "https://barefootbuttons.com/product-category/version-2/"
        }
    ]
    ```

## Running the Scrapers

### Locally (without Docker)

**Shopify Scraper:**

Navigate to the `shopify_scraper` directory:
```bash
cd shopify_scraper
```
Run the script with appropriate command-line arguments:
```bash
python Scrapping_Shop.py --db_host <your_db_host> --db_user <your_db_user> --db_password "<your_db_password>" --db_name <shopify_db_name> --stores_file_path stores.json
```
*   Replace placeholders with your actual database credentials and desired database name.
*   If `--db_password` is empty, you can omit it or pass `""`.

**WooCommerce Scraper:**

Navigate to the `woo_scraper` directory:
```bash
cd woo_scraper
```
Run the script:
```bash
python Scrapping_Woo.py --db_host <your_db_host> --db_user <your_db_user> --db_password "<your_db_password>" --db_name <woocommerce_db_name> --categories_file_path barefoot_categories.json
```
*   Replace placeholders accordingly.

### Using Docker

Dockerfiles are provided for each scraper. These are typically built and run as part of a larger CI/CD pipeline (e.g., using Jenkins and Kubernetes).

**To build an image (example for Shopify scraper):**

```bash
cd shopify_scraper
docker build -t shopify-scraper:latest .
```

**To run a container (example for Shopify scraper, connecting to a host MySQL):**

Ensure your MySQL database is accessible from Docker containers. For Minikube or Docker Desktop, `host.docker.internal` (on Mac/Windows) or your host's actual IP usually works for `DB_HOST`.

```bash
docker run -it --rm \
    -e DB_HOST="host.docker.internal" \
    -e DB_USER="your_db_user" \
    -e DB_PASSWORD="your_db_password" \
    -e DB_NAME="shopify_data" \
    -e STORES_FILE_PATH_IN_CONTAINER="stores.json" \
    shopify-scraper:latest
```
*   The `CMD` in the Dockerfile is set up to use these environment variables to construct the command-line arguments for the Python script.
*   Adjust environment variables (`-e`) as needed for your setup. The Dockerfiles define `_DEFAULT` values for these, which are then used if the runtime environment variables are not set.

## Script Arguments

Both scripts accept command-line arguments to configure database connections and input file paths. Use the `-h` or `--help` flag to see all available options:

```bash
python shopify_scraper/Scrapping_Shop.py --help
python woo_scraper/Scrapping_Woo.py --help
```

## Important Considerations

*   **Ethical Scraping:** Always be respectful of the websites you are scraping.
    *   Do not send too many requests in a short period. The scripts include `time.sleep()` calls, but you might need to adjust them.
    *   Check the website's `robots.txt` file and Terms of Service to understand their policies on scraping.
    *   Identify your scraper with a clear User-Agent string (see `REQUEST_HEADERS` in `Scrapping_Shop.py` and `HEADERS` in `Scrapping_Woo.py`).
*   **Website Structure Changes:** Web scrapers are brittle. If the target website's HTML structure changes, the scrapers might break and will need to be updated.
*   **Error Handling:** The scripts include basic error handling, but more robust mechanisms could be added for production use.
*   **Rate Limiting/IP Bans:** Aggressive scraping can lead to your IP address being blocked. Consider using proxies or rotating IP addresses for large-scale scraping (though this is beyond the scope of these basic scripts).
*   **Shopify `/products.json` Endpoint:** The Shopify scraper relies on the `/products.json` endpoint, which provides a structured way to get product data. Some stores might disable or protect this endpoint.
*   **WooCommerce Scraping:** The WooCommerce scraper performs HTML scraping, which is more prone to breaking than API-based methods. If a WooCommerce site offers a REST API and you have access, using that would be more reliable.

