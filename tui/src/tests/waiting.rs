use std::time::{Duration, Instant};

pub struct Waiting;

impl Waiting {
    pub fn until<T>(mut probe: impl FnMut() -> Option<T>) -> T {
        let deadline = Instant::now() + Duration::from_secs(10);
        loop {
            if let Some(found) = probe() {
                return found;
            }
            assert!(Instant::now() < deadline, "nothing happened within the deadline");
            std::thread::sleep(Duration::from_millis(20));
        }
    }
}
