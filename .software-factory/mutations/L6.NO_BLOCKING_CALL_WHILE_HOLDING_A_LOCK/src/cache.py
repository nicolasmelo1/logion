def refresh(lock, url):
    with lock:
        # The network call runs with every other thread queued behind it.
        payload = requests.get(url).json()
        _CACHE.update(payload)
