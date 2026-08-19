def transfer(source_lock, target_lock, amount):
    with source_lock:
        debit(amount)
        with target_lock:
            credit(amount)
