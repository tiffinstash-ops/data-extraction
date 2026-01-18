#!/bin/bash

# Shopify Order Exporter - Quick Start Script

echo "🛍️  Shopify Order Exporter"
echo "=========================="
echo ""

# Check if virtual environment exists
if [ ! -d ".venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv .venv
fi

# Activate virtual environment
echo "Activating virtual environment..."
source .venv/bin/activate

# Install dependencies
echo "Installing dependencies..."
pip install -q -r requirements.txt

# Check for environment variables
if [ -z "$SHOPIFY_ACCESS_TOKEN" ] && [ -z "$SHOPIFY_CLIENT_ID" ]; then
    echo ""
    echo "⚠️  Warning: No authentication credentials found!"
    echo ""
    echo "Please set one of the following:"
    echo "  1. SHOPIFY_ACCESS_TOKEN environment variable"
    echo "  2. SHOPIFY_CLIENT_ID and SHOPIFY_CLIENT_SECRET environment variables"
    echo ""
    echo "You can set them now or authenticate through the web interface."
    echo ""
fi

# Run Streamlit app
echo ""
echo "🚀 Starting Streamlit app..."
echo "The app will open in your browser at http://localhost:8501"
echo ""
streamlit run app.py
