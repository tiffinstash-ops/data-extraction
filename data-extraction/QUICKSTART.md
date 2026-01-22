# Shopify Order Exporter - Quick Start Guide

## 🚀 Running the Streamlit App

### Option 1: Using the start script (Easiest)
```bash
./start.sh
```

### Option 2: Manual start
```bash
streamlit run app.py
```

## 🔐 Authentication Setup

Before running the app, set up authentication using one of these methods:

### Method 1: OAuth Credentials (Recommended)
```bash
export SHOPIFY_CLIENT_ID="your_client_id_here"
export SHOPIFY_CLIENT_SECRET="your_client_secret_here"
```

### Method 2: Direct Access Token
```bash
export SHOPIFY_ACCESS_TOKEN="your_access_token_here"
```

### Method 3: Manual Entry
You can also enter your access token directly in the web interface sidebar.

## 📱 Using the Web App

1. **Launch the app** - Run `streamlit run app.py`
2. **Authenticate** - Use the sidebar to authenticate with Shopify
3. **Select dates** - Choose your start and end dates
4. **Fetch orders** - Click "Fetch Orders" button
5. **View data** - Browse the interactive table with search and filters
6. **Export** - Download as CSV or Excel

## ✨ Features

### 📊 Dashboard View
- **Total Line Items** - Count of all order line items
- **Unique Orders** - Number of distinct orders
- **Total Quantity** - Sum of all quantities
- **Unique Cities** - Number of delivery cities

### 🔍 Interactive Table
- Search across all fields
- Select which columns to display
- Sortable columns
- Responsive design

### 💾 Export Options
- **CSV Export** - Standard comma-separated values
- **Excel Export** - XLSX format with formatting

### 🎨 Beautiful UI
- Modern Shopify-inspired design
- Gradient metric cards
- Smooth animations
- Mobile responsive

## 🛠️ Command Line Alternative

If you prefer command-line usage:

```bash
# Edit main.py to set your date range
python main.py
```

## 📝 Data Fields Exported

The app exports all these fields:
- Order ID, Date, Name, Email
- Shipping address (phone, address, city, zip)
- Line item details (SKU, quantity)
- Custom Globo attributes (delivery times, instructions, etc.)

## 🐛 Troubleshooting

### "Not authenticated" error
- Check your environment variables
- Verify your credentials are correct
- Try manual token entry in the sidebar

### "No orders found"
- Verify the date range
- Check that orders exist in that period
- Ensure your access token has proper permissions

### App won't start
- Ensure all dependencies are installed: `pip install -r requirements.txt`
- Check Python version (3.8+)
- Try clearing Streamlit cache: `streamlit cache clear`

## 📞 Support

For issues or questions:
1. Check the README.md for detailed documentation
2. Review the error messages in the app
3. Verify your Shopify API credentials
