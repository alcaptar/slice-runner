use std::time::Duration;

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub struct BindingCadence {
    interval: Duration,
    limit: usize,
}

impl BindingCadence {
    pub fn new(interval: Duration, limit: usize) -> Self {
        Self { interval, limit }
    }

    pub fn interval(&self) -> Duration {
        self.interval
    }

    pub fn limit(&self) -> usize {
        self.limit
    }
}
