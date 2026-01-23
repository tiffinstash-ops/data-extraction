"""
Data models for Shopify orders.
"""
from dataclasses import dataclass
from typing import Optional, Dict, List


@dataclass
class ShippingAddress:
    """Represents a shipping address."""
    phone: Optional[str] = None
    address1: Optional[str] = None
    address2: Optional[str] = None
    city: Optional[str] = None
    zip: Optional[str] = None


@dataclass
class LineItem:
    """Represents a line item in an order."""
    title: str
    sku: Optional[str]
    quantity: int
    custom_attributes: Dict[str, str]


@dataclass
class Order:
    """Represents a Shopify order."""
    id: str
    name: str
    customer_name: Optional[str]
    created_at: str
    email: Optional[str]
    note: Optional[str]
    shipping_address: Optional[ShippingAddress]
    line_items: List[LineItem]

    @classmethod
    def from_graphql_node(cls, node: dict) -> 'Order':
        """
        Create an Order instance from a GraphQL node.
        
        Args:
            node: GraphQL order node dictionary
            
        Returns:
            Order instance
        """
        # Parse shipping address
        shipping_data = node.get('shippingAddress') or {}
        shipping_address = ShippingAddress(
            phone=shipping_data.get('phone'),
            address1=shipping_data.get('address1'),
            address2=shipping_data.get('address2'),
            city=shipping_data.get('city'),
            zip=shipping_data.get('zip')
        )
        
        # Parse customer
        customer = node.get('customer') or {}
        customer_name = customer.get('displayName')
        
        # Parse line items
        line_items = []
        for li_edge in node['lineItems']['edges']:
            item = li_edge['node']
            custom_attrs = {
                attr['key']: attr['value'] 
                for attr in item['customAttributes']
            }
            line_items.append(LineItem(
                title=item['title'],
                sku=item.get('sku'),
                quantity=item['quantity'],
                custom_attributes=custom_attrs
            ))
        
        return cls(
            id=node['id'],
            name=node['name'],
            customer_name=customer_name,
            created_at=node['createdAt'],
            email=node.get('email'),
            note=node.get('note'),
            shipping_address=shipping_address,
            line_items=line_items
        )
