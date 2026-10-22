use crate::domain::closing_reason::ClosingReason;
use crate::domain::standing::Standing;

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum Closure {
    Pending,
    InProgress,
    AwaitingMerge,
    Merged,
    Blocked(ClosingReason),
    Aborted(ClosingReason),
}

impl Closure {
    pub fn of(standing: Standing, reason: Option<ClosingReason>) -> Option<Self> {
        match (standing, reason) {
            (Standing::Pending, None) => Some(Self::Pending),
            (Standing::InProgress, None) => Some(Self::InProgress),
            (Standing::AwaitingMerge, None) => Some(Self::AwaitingMerge),
            (Standing::Merged, None) => Some(Self::Merged),
            (Standing::Blocked, Some(reason)) if reason.blocks() => Some(Self::Blocked(reason)),
            (Standing::Aborted, Some(reason)) if !reason.blocks() => Some(Self::Aborted(reason)),
            (
                Standing::Pending
                | Standing::InProgress
                | Standing::AwaitingMerge
                | Standing::Merged
                | Standing::Blocked
                | Standing::Aborted,
                _,
            ) => None,
        }
    }

    pub fn is_settled(self) -> bool {
        match self {
            Self::Blocked(_) | Self::Aborted(_) | Self::Merged => true,
            Self::Pending | Self::InProgress | Self::AwaitingMerge => false,
        }
    }

    pub fn label(self) -> String {
        match self {
            Self::Pending => "pendiente".to_string(),
            Self::InProgress => "en curso".to_string(),
            Self::AwaitingMerge => "esperando merge".to_string(),
            Self::Merged => "mergeada".to_string(),
            Self::Blocked(reason) => format!("bloqueada: {}", reason.label()),
            Self::Aborted(reason) => format!("abortada: {}", reason.label()),
        }
    }
}
