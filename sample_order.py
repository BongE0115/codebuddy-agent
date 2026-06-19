def divide(a, b):
    return a / b

def get_order(order_id):
    query = f"SELECT * FROM orders WHERE id = {order_id}"
    return execute(query)
