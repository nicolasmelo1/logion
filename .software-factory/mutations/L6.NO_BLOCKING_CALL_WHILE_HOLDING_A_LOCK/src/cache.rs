pub async fn refresh(state: &Mutex<Cache>, url: &str) {
    let mut guard = state.lock().expect("poisoned");
    // Awaiting while holding a synchronous guard: the continuation can be
    // scheduled onto a thread that then blocks on this same lock.
    let payload = fetch(url).await;
    guard.insert(payload);
}
