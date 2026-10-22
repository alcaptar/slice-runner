use std::time::{Instant, SystemTime, UNIX_EPOCH};

use crate::domain::clock::Clock;
use crate::domain::wall_clock::WallClock;

pub struct SystemClock;

impl Clock for SystemClock {
    fn now(&self) -> Instant {
        Instant::now()
    }
}

impl WallClock for SystemClock {
    fn epoch_millis(&self) -> u64 {
        SystemTime::now()
            .duration_since(UNIX_EPOCH)
            .map_or(0, |since| u64::try_from(since.as_millis()).unwrap_or(u64::MAX))
    }
}
