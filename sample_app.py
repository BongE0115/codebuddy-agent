def add(a,b):
    return a+b

def get_user(id):
    query = f"SELECT * FROM users WHERE id = {id}"
    return execute(query)
