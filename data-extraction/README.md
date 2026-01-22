# Shopify Order Exporter

A Python application to export Shopify orders with custom attributes (Globo) to CSV format.

## Project Structure

```
.
├── app.py              # Streamlit web application (recommended)
├── config.py           # Configuration settings (API URL, headers, etc.)
├── constants.py        # Constants (CSV fields, GraphQL queries)
├── models.py           # Data models (Order, LineItem, ShippingAddress)
├── utils.py            # Utility functions (data cleaning, formatting)
├── shopify_client.py   # Shopify API client
├── auth.py             # OAuth authentication
├── exporter.py         # CSV export functionality
├── get_token.py        # Standalone token retrieval script
├── main.py             # Command-line entry point
├── requirements.txt    # Python dependencies
└── README.md           # This file
```

## Setup

1. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

2. **Configure authentication:**

   You have two options for authentication:

   **Option A: Use OAuth Client Credentials (Recommended)**
   
   Set your OAuth credentials as environment variables:
   ```bash
   export SHOPIFY_CLIENT_ID="your_client_id_here"
   export SHOPIFY_CLIENT_SECRET="your_client_secret_here"
   ```
   
   Then retrieve your access token:
   ```bash
   python get_token.py
   ```
   
   The script will display your access token and provide instructions on how to save it.

   **Option B: Use Pre-existing Access Token**
   
   If you already have an access token, set it as an environment variable:
   ```bash
   export SHOPIFY_ACCESS_TOKEN="your_access_token_here"
   ```
   
   Or edit `config.py` and add it directly:
   ```python
   ACCESS_TOKEN = "your_access_token_here"
   ```

## Usage

### Streamlit Web App (Recommended)

Run the interactive web application:
```bash
streamlit run app.py
```

This will open a web interface where you can:
- Authenticate with Shopify
- Select custom date ranges using a date picker
- View orders in an interactive table
- Search and filter results
- See order statistics and metrics
- Download data as CSV or Excel

### Command Line Usage

Run the main script:
```bash
python main.py
```

By default, this will export orders from the date range specified in `main.py`.

### Custom Date Range

Edit `main.py` to change the date range:
```python
start_date = "2026-01-13"
end_date = "2026-01-14"
```

### Custom Output Filename

```python
fetch_and_export("2026-01-13", "2026-01-14", "my_orders.csv")
```

### Programmatic Usage

```python
from exporter import fetch_and_export

# Export orders
fetch_and_export("2026-01-13", "2026-01-14")
```

## Features

- **🌐 Web Interface**: Interactive Streamlit app with date pickers and data visualization
- **🔐 OAuth Authentication**: Automatic access token retrieval using client credentials
- **📊 Data Visualization**: View order statistics and metrics in real-time
- **🔍 Search & Filter**: Interactive table with search and column selection
- **💾 Multiple Export Formats**: Download as CSV or Excel
- **📄 Pagination Support**: Automatically handles Shopify API pagination
- **⏱️ Rate Limiting**: Built-in delays to respect API rate limits
- **🎨 Custom Attributes**: Exports Globo custom attributes
- **🧹 Data Cleaning**: Replaces null/empty values with 0
- **🌍 Timezone Support**: Configurable timezone (default: US/Eastern)

## CSV Output

The exported CSV includes the following fields:
- Order details (ID, date, name, email)
- Shipping information (address, phone, city, zip)
- Line item details (SKU, quantity)
- Custom attributes (delivery instructions, times, etc.)

## Configuration

### API Settings (`config.py`)
- `SHOPIFY_URL`: Your Shopify GraphQL API endpoint
- `ACCESS_TOKEN`: Your Shopify access token
- `API_DELAY_SECONDS`: Delay between API requests (default: 0.5s)

### Timezone (`config.py`)
- `TIMEZONE`: Timezone for date filtering (default: 'US/Eastern')

## Error Handling

The application will print error messages if:
- API requests fail (non-200 status codes)
- Authentication fails
- Network issues occur

## Security Note

**Important**: Never commit your `ACCESS_TOKEN` to version control. Consider using:
- Environment variables
- `.env` files (with `.gitignore`)
- Secret management services

## License

MIT
