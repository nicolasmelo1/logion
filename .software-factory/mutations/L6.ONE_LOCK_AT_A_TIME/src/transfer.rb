def transfer(source_lock, target_lock, amount)
  source_lock.synchronize do
    debit(amount)
    target_lock.synchronize do
      credit(amount)
    end
  end
end
