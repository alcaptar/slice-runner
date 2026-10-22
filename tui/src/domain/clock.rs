use std::time::Instant;

pub trait Clock: Send + Sync {
    fn now(&self) -> Instant;
}
