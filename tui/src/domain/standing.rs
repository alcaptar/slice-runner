#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum Standing {
    Pending,
    InProgress,
    AwaitingMerge,
    Blocked,
    Aborted,
    Merged,
}

impl Standing {
    pub fn parse(text: &str) -> Option<Self> {
        match text {
            "pending" => Some(Self::Pending),
            "in-progress" => Some(Self::InProgress),
            "awaiting-merge" => Some(Self::AwaitingMerge),
            "blocked" => Some(Self::Blocked),
            "aborted" => Some(Self::Aborted),
            "merged" => Some(Self::Merged),
            _ => None,
        }
    }
}
