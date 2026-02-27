import json
import boto3
import time
import os
from datetime import datetime, timedelta
from decimal import Decimal

# Helper class to convert DynamoDB Decimal to JSON serializable
class DecimalEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, Decimal):
            return float(obj)
        return super(DecimalEncoder, self).default(obj)

# Initialize DynamoDB
dynamodb = boto3.resource('dynamodb')
table_name = os.environ.get('TABLE_NAME')
table = dynamodb.Table(table_name)

# In-memory cache
cache = {}
CACHE_TTL = int(os.environ.get('CACHE_TTL', 60))

def get_from_cache(key):
    if key in cache:
        item, timestamp = cache[key]
        if datetime.now() - timestamp < timedelta(seconds=CACHE_TTL):
            return item
        else:
            del cache[key]
    return None

def set_in_cache(key, value):
    cache[key] = (value, datetime.now())

def lambda_handler(event, context):
    print("Event received:", json.dumps(event))  # Debug log
    
    http_method = event.get('httpMethod', '')
    path = event.get('path', '')
    
    start_time = time.time()
    cache_hit = False
    
    try:
        # POST - Create new product
        if http_method == 'POST' and path == '/products':
            print("Processing POST request")
            
            # Parse the request body
            body = json.loads(event.get('body', '{}'))
            product_id = body.get('productID', f"product-{int(time.time())}")
            
            # Create item for DynamoDB
            item = {
                'productID': product_id,
                'name': body.get('name', 'New Product'),
                'price': Decimal(str(body.get('price', 0))),
                'category': body.get('category', 'general'),
                'inStock': body.get('inStock', True),
                'created_at': int(time.time())
            }
            
            # Add optional fields
            if 'description' in body:
                item['description'] = body.get('description')
            
            print(f"Writing to DynamoDB: {item}")
            
            # Write to DynamoDB
            table.put_item(Item=item)
            
            # INVALIDATE CACHE
            cache_keys_cleared = []
            if 'all_products' in cache:
                del cache['all_products']
                cache_keys_cleared.append('all_products')
            
            product_cache_key = f"product_{product_id}"
            if product_cache_key in cache:
                del cache[product_cache_key]
                cache_keys_cleared.append(product_cache_key)
            
            response_time = (time.time() - start_time) * 1000
            
            return {
                'statusCode': 201,
                'headers': {
                    'Content-Type': 'application/json',
                    'Access-Control-Allow-Origin': '*',
                    'X-Response-Time': str(round(response_time, 2))
                },
                'body': json.dumps({
                    'message': 'Product created successfully',
                    'productID': product_id,
                    'cache_invalidated': cache_keys_cleared,
                    'response_time_ms': round(response_time, 2)
                })
            }
        
        # GET all products
        elif http_method == 'GET' and path == '/products':
            cache_key = "all_products"
            
            cached_items = get_from_cache(cache_key)
            if cached_items:
                items = cached_items
                cache_hit = True
                source = "CACHE HIT"
            else:
                response = table.scan()
                items = response.get('Items', [])
                set_in_cache(cache_key, items)
                source = "CACHE MISS (DB)"
            
            response_time = (time.time() - start_time) * 1000
            
            return {
                'statusCode': 200,
                'headers': {
                    'Content-Type': 'application/json',
                    'X-Response-Time': str(round(response_time, 2)),
                    'X-Cache-Hit': str(cache_hit),
                    'Access-Control-Allow-Origin': '*'
                },
                'body': json.dumps({
                    'items': items,
                    'count': len(items),
                    'response_time_ms': round(response_time, 2),
                    'cache_hit': cache_hit,
                    'source': source
                }, cls=DecimalEncoder)
            }
        
        # GET single product
        elif http_method == 'GET' and path.startswith('/products/'):
            product_id = path.split('/')[-1]
            cache_key = f"product_{product_id}"
            
            cached_item = get_from_cache(cache_key)
            if cached_item:
                item = cached_item
                cache_hit = True
                source = "CACHE HIT"
            else:
                response = table.get_item(Key={'productID': product_id})
                item = response.get('Item', {})
                set_in_cache(cache_key, item)
                source = "CACHE MISS (DB)"
            
            response_time = (time.time() - start_time) * 1000
            
            return {
                'statusCode': 200,
                'headers': {
                    'Content-Type': 'application/json',
                    'X-Response-Time': str(round(response_time, 2)),
                    'X-Cache-Hit': str(cache_hit),
                    'Access-Control-Allow-Origin': '*'
                },
                'body': json.dumps({
                    'item': item,
                    'response_time_ms': round(response_time, 2),
                    'cache_hit': cache_hit,
                    'source': source
                }, cls=DecimalEncoder)
            }
        
        # Handle any other routes
        else:
            print(f"No handler for {http_method} {path}")
            return {
                'statusCode': 404,
                'headers': {
                    'Access-Control-Allow-Origin': '*'
                },
                'body': json.dumps({'error': f'Not found: {http_method} {path}'})
            }
            
    except Exception as e:
        print("Error:", str(e))
        return {
            'statusCode': 500,
            'headers': {
                'Access-Control-Allow-Origin': '*'
            },
            'body': json.dumps({'error': str(e)})
        }