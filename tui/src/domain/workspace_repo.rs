#[derive(Debug, Clone, PartialEq, Eq)]
pub enum WorkspaceRepo {
    Unknown,
    Known(String),
}
