pub trait WallClock {
    fn epoch_millis(&self) -> u64;
}
