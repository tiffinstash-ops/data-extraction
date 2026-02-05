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
    "PREMIUM COVERAGE", 
    "PREMIUM VALUE", 
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

SHEET_URLS = [
            "https://docs.google.com/spreadsheets/d/1jhVzSKqioPpIIkofA5vgi6CmoffNasnFI_ethmtYQnA/edit#gid=0",
            "https://docs.google.com/spreadsheets/d/1GsH_HfzD82BKcKZFTNAD9_QhzjFOmbCN-ns6HFSxVtU/edit#gid=970833819",
            "https://docs.google.com/spreadsheets/d/13W_AHYZvmVZ8l39FMEqgNUAmMNc8XWr1upNnW9yLZZ0/edit#gid=1512008922",
            "https://docs.google.com/spreadsheets/d/1oELK2617pw12RnuWIuDicM3HGWnhWPCWAygAbD22SiE/edit#gid=0",
            "https://docs.google.com/spreadsheets/d/17lIPtH03ifOtuNIYyla4AgTBySqIN5S9e9-TGaXYkX8/edit#gid=1305583510",
            "https://docs.google.com/spreadsheets/d/1_-OI3N7Vfo4ItUFklQTBzk6HwPdQBW9mBarxp8On2-c/edit#gid=0",
            "https://docs.google.com/spreadsheets/d/1Y8eAUN_nRinDpjcfC1vXgRl-G3ZpMAEs6OpFKVAkBgE/edit#gid=0",
            "https://docs.google.com/spreadsheets/d/1LKfqjXqfOzDXjKIlGg6MJRUSMRCEJxOTRYgE_Jx4X70/edit#gid=0",
            "https://docs.google.com/spreadsheets/d/1eNH9cWIYELQy0Bt1xOTRxgoQm4EOFmD9WBjOQZj2tVE/edit#gid=651157510",
            "https://docs.google.com/spreadsheets/d/1ELDyinkFn8FTr6lLm5M9LtgSwlUWhsJfRfZM40N5QRA/edit#gid=827866219",
            "https://docs.google.com/spreadsheets/d/1CdxAz_GSN2DznFlGH8L79wQns8-E1aXcAhmizw0CKN8/edit#gid=665160349",
            "https://docs.google.com/spreadsheets/d/1tSj5rq1fSRh0eYM_JkYG5knWqDWHk9WDSuJd-6M3c-Q/edit?gid=1419491760#gid=1419491760",
            "https://docs.google.com/spreadsheets/d/1AWxnyHDHE6V6qncT2KLiQKKHoZUAfS1v4FLlkit_MV4/edit?gid=0#gid=0",
            "https://docs.google.com/spreadsheets/d/1NExFM0v0X05CuFy45tI-7Y8tRiQASXNIz_ZTHQQG8PM/edit?gid=1080379805#gid=1080379805",
            "https://docs.google.com/spreadsheets/d/1WwE_yJPRfRiOwZx9-gztRQHDdHFRb3a9UBwxlHELkJ0/edit?gid=806624255#gid=806624255",
            "https://docs.google.com/spreadsheets/d/1jj_itR-lzCJFX_GXdHyo5Wb7gUym6Sq3dXiAXA7h-WE/edit?gid=1256840260#gid=1256840260",
            "https://docs.google.com/spreadsheets/d/1tXlSUbaJc4CTMuKr7hsZEs3RgZaPAegSc99CepGxJcY/edit?gid=418342002#gid=418342002",
            "https://docs.google.com/spreadsheets/d/1fdNpm7-OMZ7gqAs_PLwfUFskO-hzPEK_EKuyv-zqaLo/edit?gid=322494704#gid=322494704",
            "https://docs.google.com/spreadsheets/d/1g6vgb-75RQNK2ZR3bWNBCod_w-hkvfq9Iq2sbXz5b7g/edit?gid=1436690804#gid=1436690804",
            "https://docs.google.com/spreadsheets/d/1cxvPilQfarTbaK2uwIxCsOspc03O6XHHyOTLPZ8f-kw/edit?gid=2066185487#gid=2066185487",
            "https://docs.google.com/spreadsheets/d/1A84PGh6Amu5t3BDfMUnJJHhQFAaEXV21t0SxVNxihDc/edit?gid=1557160656#gid=1557160656",
            "https://docs.google.com/spreadsheets/d/1iKCWiBAQTxaJUSrqZMBOPNN2b-J5P09pZ0ttIQX6HRY/edit?gid=1154132398#gid=1154132398",
            "https://docs.google.com/spreadsheets/d/13Gg3wEDXQalZX3S14R5GX20GWSt3J8zxFNT05QAZ_us/edit?gid=1525030672#gid=1525030672",
            "https://docs.google.com/spreadsheets/d/1sFALY7uM4HkcxErJf-1m0o_SCQwVLH31b_8ofMhSjrw/edit?gid=1051101325#gid=1051101325",
            "https://docs.google.com/spreadsheets/d/1URRvcwxLmFBHqF0dx83T2yf1U3RVou8-l9vWqcWP314/edit?gid=1728117777#gid=1728117777",
            "https://docs.google.com/spreadsheets/d/1EacU4rH_it3h_T6DIEzNu1D92ljje9Sfuxcn5U3hsCQ/edit?gid=914036751#gid=914036751",
            "https://docs.google.com/spreadsheets/d/1BoMQuVhUZynWyUcOvst689J_1cMDsjuKT04Tt1bs_nk/edit?gid=1248933880#gid=1248933880",
            "https://docs.google.com/spreadsheets/d/1veyj-IYS48EG39q_MeR8oHfYh8AC--UrRstwIls7UXU/edit?gid=844031492#gid=844031492",
            "https://docs.google.com/spreadsheets/d/1gCqHRAITQ7yYQNp4w4ZuUO_ngs0oqLjZY8dLUD6n_9Y/edit?gid=1309156205#gid=1309156205",
            "https://docs.google.com/spreadsheets/d/10wxHMiDqgtlf1d2HGkR52Pp39Cmm5LN6-2HMQe0UjOU/edit?gid=1926170742#gid=1926170742",
            "https://docs.google.com/spreadsheets/d/1GbWszea0_l0Am67vAL_rN4_F0msh04DIqSezCYs-6to/edit?gid=1540819288#gid=1540819288",
            "https://docs.google.com/spreadsheets/d/1ff9sfvlZMvRdpjFfUReu741Qp10wiyL0-duBzs61otY/edit?gid=378708161#gid=378708161",
            "https://docs.google.com/spreadsheets/d/1KWvWtqy5x0QGHfKR0pr4KFVeKlGkFWQZ_F5BkIzjGag/edit?gid=320419593#gid=320419593",
            "https://docs.google.com/spreadsheets/d/1IS9htxNu6vm-1wHQKJMOYhmdTmhFA_lRXXgRgHVGPqc/edit?gid=1827559066#gid=1827559066",
            "https://docs.google.com/spreadsheets/d/1cjONOvM8hVmfUDyF_PcXXKe-kRwadj2GHJyf-2dnfAc/edit?gid=1196381786#gid=1196381786",
            "https://docs.google.com/spreadsheets/d/1ss0E87FV-dIPOq4SjpXEczkVXvH_5O1bbMUBU3UF2UQ/edit?gid=1545022801#gid=1545022801",
            "https://docs.google.com/spreadsheets/d/159fRwl-eceU2JBX1KCwHyaLbbwPyRlKLYpQH0O0-xj0/edit?gid=2053044332#gid=2053044332",
            "https://docs.google.com/spreadsheets/d/1N5RjaE8yoWyKuvItpj77XxGN6vl6sO1vO4iZgBJpkb0/edit?gid=2032633298#gid=2032633298",
            "https://docs.google.com/spreadsheets/d/19f2httSK9nayvzhkArLqMYwQ-9V_B82qdvt1587vmFY/edit?gid=2106041640#gid=2106041640",
            "https://docs.google.com/spreadsheets/d/1UxBRxekUv9j5YkMU3o0V2XZjXM2hNPfogK48RTht3u8/edit?gid=2115892785#gid=2115892785"
        ]