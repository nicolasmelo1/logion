def price(order):
    total = 0
    if order.a:
        total += 1
    if order.b:
        total += 1
    if order.c:
        total += 1
    if order.d:
        total += 1
    if order.e:
        total += 1
    return total
