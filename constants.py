"""
Constants used throughout the application.
"""

# CSV Field Names
CSV_FIELDNAMES = [
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
