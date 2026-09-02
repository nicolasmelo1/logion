def price(order)
  total = 0
  total += 1 if order.a
  total += 1 if order.b
  total += 1 if order.c
  total += 1 if order.d
  total += 1 if order.e
  total
end
