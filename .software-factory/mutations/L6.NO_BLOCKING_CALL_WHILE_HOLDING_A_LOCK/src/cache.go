package cache

func Refresh(mu *sync.Mutex) {
	mu.Lock()
	defer mu.Unlock()
	// Every other goroutine queues behind this sleep.
	time.Sleep(2 * time.Second)
}
