import json
import boto3
import time
import os
from decimal import Decimal

# Helper class to convert DynamoDB Decimal to JSON serializable
class DecimalEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, Decimal):
            return float(obj)  # Convert Decimal to float
        return super(DecimalEncoder, self).default(obj)

# Initialize DynamoDB
dynamodb = boto3.resource('dynamodb')
table_name = os.environ.get('TABLE_NAME')
table = dynamodb.Table(table_name)

def lambda_handler(event, context):
    """
    API Endpoints:
    GET /products - List all products
    GET /products/{id} - Get single product
    POST /products - Create product (for testing)
    """
    http_method = event.get('httpMethod', '')
    path = event.get('path', '')
    
    # Start timing
    start_time = time.time()
    
    try:
        # GET all products
        if http_method == 'GET' and path == '/products':
            response = table.scan()
            items = response.get('Items', [])
            
            # Calculate response time
            response_time = (time.time() - start_time) * 1000
            
            return {
                'statusCode': 200,
                'headers': {
                    'Content-Type': 'application/json',
                    'X-Response-Time': str(round(response_time, 2)),
                    'Access-Control-Allow-Origin': '*'
                },
                'body': json.dumps({
                    'items': items,
                    'count': len(items),
                    'response_time_ms': round(response_time, 2)
                }, cls=DecimalEncoder)  # Use DecimalEncoder here!
            }
        
        # GET single product
        elif http_method == 'GET' and path.startswith('/products/'):
            product_id = path.split('/')[-1]
            
            response = table.get_item(Key={'productID': product_id})
            item = response.get('Item', {})
            
            response_time = (time.time() - start_time) * 1000
            
            return {
                'statusCode': 200,
                'headers': {
                    'Content-Type': 'application/json',
                    'X-Response-Time': str(round(response_time, 2)),
                    'Access-Control-Allow-Origin': '*'
                },
                'body': json.dumps({
                    'item': item,
                    'response_time_ms': round(response_time, 2)
                }, cls=DecimalEncoder)  # Use DecimalEncoder here!
            }
        
        # POST new product (for invalidation testing)
        elif http_method == 'POST' and path == '/products':
            body = json.loads(event.get('body', '{}'))
            product_id = body.get('productID', f"product-{int(time.time())}")
            
            item = {
                'productID': product_id,
                'name': body.get('name', 'New Product'),
                'price': Decimal(str(body.get('price', 0))),  # Convert to Decimal
                'category': body.get('category', 'general'),
                'created_at': int(time.time())
            }
            
            table.put_item(Item=item)
            
            return {
                'statusCode': 201,
                'headers': {
                    'Access-Control-Allow-Origin': '*'
                },
                'body': json.dumps({
                    'message': 'Product created',
                    'productID': product_id
                })
            }
        
        else:
            return {
                'statusCode': 404,
                'body': json.dumps({'error': 'Not found'})
            }
            
    except Exception as e:
        return {
            'statusCode': 500,
            'body': json.dumps({'error': str(e)})
        }