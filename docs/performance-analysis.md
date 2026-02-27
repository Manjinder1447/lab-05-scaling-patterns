# Lab 5 Part 2 - Caching Implementation Analysis

Student: Manjinder Kaur  
Student ID: 991800063  
Date: February 27, 2026

---

## 1. What I Built

For this lab, I created a serverless API on AWS that stores product information and tested how caching affects performance.

### AWS Services I Used
- DynamoDB- A database table called "Products" with productID as the primary key. I added 3 items: iPhone 15 Pro Max, Samsung Galaxy S24, and Sony Headphones
- Lambda- Two Python functions: one without caching (for baseline testing) and one with in-memory caching
- API Gateway - Created REST API with endpoints to get all products, get one product, and add new products
- IAM Role- Used the pre-configured LabRole from AWS Academy (so I didn't have to mess with permissions)

### How I Set Up Caching
- Cache Type: Simple in-memory dictionary inside the Lambda function (not fancy, but works for demo)
- Cache TTL:60 seconds (data expires after 1 minute)
- How it works: When someone requests a product, I check the cache first. If it's there, return it super fast. If not, get it from DynamoDB and store it in cache for next time.

### My API Endpoints
| Endpoint      | Method | What it does |
|---------------|--------|--------------|
| `/products`   | GET    | Returns all products in the table |
| `/products/1` | GET    | Returns just the iPhone (or whatever ID you put) |
| `/products`   | POST   | Adds a new product or updates existing one |

---

## 2. Testing Without Cache (Baseline)

First, I tested my uncached Lambda function to see how slow it was normally. I hit the `/products/1` endpoint 5 times and recorded the response times.

### Results for iPhone (product ID: 1)

| Request # | Time (ms) |
|-----------|-----------|
| 1         | 51.80     |
| 2         | 20.52     |
| 3         | 19.97     |
| 4         | 21.45     |
| 5         | 19.97     |
| Average   | 26.74 ms  |

### Other Tests
- Getting **all products** (scanning the whole table): **272.64 ms** (much slower!)
- Samsung Galaxy (ID: 2): **11.51 ms**
- Sony Headphones (ID: 3): **9.19 ms**

What I noticed:The first request is slower (probably Lambda cold start), but after that it's pretty consistent around 20ms.

## 3. Testing With Cache

Then I switched to my cached Lambda function and ran the same tests.

### Results for iPhone (with caching)

| Request # | Time (ms) | Cache Status | Where data came from |
|-----------|-----------|--------------|---------------------|
| 1 | 264.67 | MISS | DynamoDB (and then stored in cache) |
| 2 | 0.02 | HIT | Cache memory |
| 3 | 0.02 | HIT | Cache memory |
| 4 | 0.02 | HIT | Cache memory |
| 5 | 0.02 | HIT | Cache memory |
| **Average** | **52.95 ms** | **Hit Rate: 80%** | |

### What's Interesting
- The first request is SUPER slow(264ms) because it has to read from database AND store in cache
- After that, all requests are basically instant (0.02ms - I can't even measure it properly!)
- So for 5 requests, I only hit the database once instead of 5 times


## 4. Comparing Before and After

| Metric | Without Cache | With Cache | Improvement |
|--------|--------------|------------|-------------|
| Average time | 26.74 ms | 52.95 ms | Actually got worse! |
| Fastest request | 19.97 ms | 0.02 ms | 99.9% faster |
| Slowest request | 51.80 ms | 264.67 ms | First request penalty |
| Database hits for 5 requests | 5 times | 1 time | 80% less database load |

*\*The average looks worse with cache because that first request is so slow. If I did 100 requests, the average would be super low because 99 of them would be 0.02ms. This shows why cache warming is important in real apps!*

---

## 5. Testing Cache Invalidation (Does it clear when I add stuff?)

I created a test product to see if the cache clears when I add/update data.

### My Test Steps

| Step | What I Did                             | Response Time | Cache Status | Did it work?           |
|------|----------------------------------------|---------------|--------------|------------------------|
| 1    | Created product "test-999" with POST   | N/A           | -            |  Created               |
| 2    | Got the product first time             | 39.05 ms      | MISS         |  Cache populated       |
| 3    | Got it again right away                | 0.02 ms       | HIT          |  Working!              |
| 4    | Got it a third time                    | 0.02 ms       | HIT          | Still cached           |
| 5    | Tried to update it (change name/price) | N/A           | -            | Cache cleared          |
| 6    | Got it after update                    | 0.11 ms       | HIT          | BUT data didn't change!|
| 7    | Got it again                           | 0.02 ms       | HIT          | Still old data         |

### What Went Wrong

When I tried to update the product, the POST request said "Product created" but when I got it again, the name and price were still the old ones. Looking at my DynamoDB, I actually had **two entries** with the same ID:

```json
{
  "items": [
    {"productID": "2", "name": "Samsung Galaxy S24"},
    {"productID": "test-999", "name": "Test Product", "price": 49.99},  // Old one
    {"productID": "test-999", "name": "UPDATED PRODUCT", "price": 59.99}, // New one??
    {"productID": "1", "name": "Apple iPhone 15 Pro Max"},
    {"productID": "3", "name": "Sony WH-1000XM4 Headphones"}
  ]
}