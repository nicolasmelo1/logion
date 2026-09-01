def refresh(lock, url)
  lock.synchronize do
    # Every other thread queues behind this network call.
    payload = Net::HTTP.get(URI(url))
    CACHE.update(payload)
  end
end
