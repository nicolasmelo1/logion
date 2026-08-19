pub fn transfer(from: &Mutex<Account>, to: &Mutex<Account>, amount: u64) {
    let mut source = from.lock().expect("poisoned");
    let mut target = to.lock().expect("poisoned");
    source.balance -= amount;
    target.balance += amount;
}
