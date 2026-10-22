#[derive(Debug, Clone, PartialEq, Eq)]
pub enum UpdateProgress {
    Running,
    Installed,
    Failed(String),
}
