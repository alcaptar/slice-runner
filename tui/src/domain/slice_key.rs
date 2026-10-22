use crate::domain::follow_line::FollowLine;

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct SliceKey {
    repo: String,
    issue: u64,
}

impl SliceKey {
    pub fn new(repo: &str, issue: u64) -> Self {
        Self {
            repo: repo.to_string(),
            issue,
        }
    }

    pub fn of(line: &FollowLine) -> Self {
        Self::new(line.repo(), line.issue())
    }
}
