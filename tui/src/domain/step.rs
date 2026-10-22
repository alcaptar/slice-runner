#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum Step {
    MountWorktree,
    Understand,
    Implement,
    RunControls,
    Verify,
    OpenPullRequest,
    AwaitCi,
    CatchUp,
    AwaitMerge,
}

impl Step {
    pub fn parse(text: &str) -> Option<Self> {
        match text {
            "mount-worktree" => Some(Self::MountWorktree),
            "understand" => Some(Self::Understand),
            "implement" => Some(Self::Implement),
            "run-controls" => Some(Self::RunControls),
            "verify" => Some(Self::Verify),
            "open-pull-request" => Some(Self::OpenPullRequest),
            "await-ci" => Some(Self::AwaitCi),
            "catch-up" => Some(Self::CatchUp),
            "await-merge" => Some(Self::AwaitMerge),
            _ => None,
        }
    }

    pub fn name(self) -> &'static str {
        match self {
            Self::MountWorktree => "mount-worktree",
            Self::Understand => "understand",
            Self::Implement => "implement",
            Self::RunControls => "run-controls",
            Self::Verify => "verify",
            Self::OpenPullRequest => "open-pull-request",
            Self::AwaitCi => "await-ci",
            Self::CatchUp => "catch-up",
            Self::AwaitMerge => "await-merge",
        }
    }
}
