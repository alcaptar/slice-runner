use std::fmt;
use std::time::Duration;

#[derive(Debug, Clone, PartialEq, Eq)]
pub enum FollowLineRejected {
    NotJson { line: String },
    WrongValue { key: String, reason: String },
    UnsupportedVersion { version: u64 },
    UnknownKind { kind: String },
    FollowEnded,
    FollowNotLaunched { reason: String },
}

impl fmt::Display for FollowLineRejected {
    fn fmt(&self, formatter: &mut fmt::Formatter<'_>) -> fmt::Result {
        match self {
            Self::NotJson { line } => write!(formatter, "line is not a JSON object: {line}"),
            Self::WrongValue { key, reason } => write!(formatter, "wrong value for `{key}`: {reason}"),
            Self::UnsupportedVersion { version } => write!(formatter, "unsupported follow line version {version}"),
            Self::UnknownKind { kind } => write!(formatter, "unknown follow line kind `{kind}`"),
            Self::FollowEnded => write!(formatter, "slice-runner follow ended"),
            Self::FollowNotLaunched { reason } => write!(formatter, "could not launch slice-runner follow: {reason}"),
        }
    }
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct WorkspaceIdRejected {
    pub text: String,
}

impl fmt::Display for WorkspaceIdRejected {
    fn fmt(&self, formatter: &mut fmt::Formatter<'_>) -> fmt::Result {
        write!(formatter, "workspace id is not a uuid: {}", self.text)
    }
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct SessionNotLaunched {
    pub reason: String,
}

impl fmt::Display for SessionNotLaunched {
    fn fmt(&self, formatter: &mut fmt::Formatter<'_>) -> fmt::Result {
        write!(formatter, "could not launch the claude session: {}", self.reason)
    }
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub enum IssuesUnread {
    TimedOut { budget: Duration },
    CommandFailed { reason: String },
    NotJson { output: String },
    WrongValue { key: String, reason: String },
}

impl fmt::Display for IssuesUnread {
    fn fmt(&self, formatter: &mut fmt::Formatter<'_>) -> fmt::Result {
        match self {
            Self::TimedOut { budget } => write!(formatter, "gh did not finish within {budget:?}"),
            Self::CommandFailed { reason } => write!(formatter, "gh failed: {reason}"),
            Self::NotJson { output } => write!(formatter, "gh did not answer with JSON: {output}"),
            Self::WrongValue { key, reason } => write!(formatter, "wrong value for `{key}` from gh: {reason}"),
        }
    }
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub enum ComparisonNotOpened {
    TimedOut { budget: Duration },
    CommandFailed { reason: String },
}

impl fmt::Display for ComparisonNotOpened {
    fn fmt(&self, formatter: &mut fmt::Formatter<'_>) -> fmt::Result {
        match self {
            Self::TimedOut { budget } => write!(formatter, "open did not finish within {budget:?}"),
            Self::CommandFailed { reason } => write!(formatter, "open failed: {reason}"),
        }
    }
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub enum WorkspaceNotReopened {
    Unmarked { parent: u64 },
    Unread(IssuesUnread),
}

impl fmt::Display for WorkspaceNotReopened {
    fn fmt(&self, formatter: &mut fmt::Formatter<'_>) -> fmt::Result {
        match self {
            Self::Unmarked { parent } => write!(formatter, "parent #{parent} was not designed in a workspace"),
            Self::Unread(unread) => write!(formatter, "could not read the parent: {unread}"),
        }
    }
}

impl From<IssuesUnread> for WorkspaceNotReopened {
    fn from(unread: IssuesUnread) -> Self {
        Self::Unread(unread)
    }
}
