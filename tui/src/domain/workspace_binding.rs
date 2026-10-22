use crate::domain::parent::Parent;
use crate::domain::slice_row::SliceRow;

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum WorkspaceBinding {
    Unbound,
    Bound(u64),
}

impl WorkspaceBinding {
    pub fn admits(self, row: &SliceRow, repo: &str) -> bool {
        match self {
            Self::Unbound => false,
            Self::Bound(parent) => row.repo() == repo && row.parent() == Parent::Issue(parent),
        }
    }
}
