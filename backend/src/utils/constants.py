"""
Constants used throughout the application.
"""

# Shopify Order Field Names
SHOPIFY_ORDER_FIELDNAMES = [
    "ORDER ID",
    "DATE",
    "NAME",
    "Shipping address phone numeric",
    "phone_edit",
    "EMAIL",
    "HOUSE UNIT NO",
    "ADDRESS LINE 1",
    "Select Delivery City",
    "Shipping address city",
    "ZIP",
    "SKU",
    "Delivery Instructions (for drivers)",
    "Order Instructions (for sellers)",
    "Delivery Time",
    "Dinner Delivery",
    "Lunch Delivery",
    "Lunch Delivery Time",
    "Lunch Time",
    "Delivery between",
    "deliverytime_edit",
    "QUANTITY",
    "Select Start Date",
    "Delivery city"
]

# Seller Field Names
SELLER_FIELDNAMES = [
    "ORDER ID", 
    "DATE", 
    "NAME", 
    "PHONE", 
    "EMAIL", 
    "HOUSE UNIT NO", 
    "ADDRESS LINE 1", 
    "CITY", 
    "ZIP", 
    "SKU", 
    "SELLER", 
    "DELIVERY", 
    "MEAL TYPE", 
    "MEAL PLAN", 
    "PRODUCT", 
    "FLABL", 
    "CLABL", 
    "LABEL", 
    "DRIVER NOTE", 
    "SELLER NOTE", 
    "UPSTAIR DELIVERY", 
    "DELIVERY TIME", 
    "QUANTITY", 
    "ONGOING", 
    # "PREMIUM COVERAGE", 
    # "PREMIUM VALUE", 
]

# GraphQL Query
ORDERS_QUERY = """
query GetOrders($cursor: String, $query: String) {
  orders(first: 50, after: $cursor, query: $query) {
    pageInfo {
      hasNextPage
      endCursor
    }
    edges {
      node {
        id
        name
        createdAt
        email
        customer {
          displayName
        }
        note
        shippingAddress {
          phone
          address1
          address2
          city
          zip
        }
        lineItems(first: 20) {
          edges {
            node {
              title
              sku
              quantity
              customAttributes {
                key
                value
              }
            }
          }
        }
      }
    }
  }
}
"""

FOLDER_ID = '1t5s3Zf5nGOceskozz74tta9H5vd9mawp'

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive.metadata.readonly"
]
