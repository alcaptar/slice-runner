use std::fmt;

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub struct Elapsed {
    millis: u64,
}

impl Elapsed {
    const SECOND: u64 = 1_000;
    const MINUTE: u64 = 60 * Self::SECOND;
    const HOUR: u64 = 60 * Self::MINUTE;
    const DAY: u64 = 24 * Self::HOUR;

    pub fn between(earlier: u64, later: u64) -> Self {
        Self {
            millis: later.saturating_sub(earlier),
        }
    }
}

impl fmt::Display for Elapsed {
    fn fmt(&self, formatter: &mut fmt::Formatter<'_>) -> fmt::Result {
        let millis = self.millis;
        if millis < Self::MINUTE {
            write!(formatter, "{}s", millis / Self::SECOND)
        } else if millis < Self::HOUR {
            write!(formatter, "{}m", millis / Self::MINUTE)
        } else if millis < Self::DAY {
            write!(
                formatter,
                "{}h {}m",
                millis / Self::HOUR,
                millis % Self::HOUR / Self::MINUTE
            )
        } else {
            write!(formatter, "{}d", millis / Self::DAY)
        }
    }
}
