#[derive(Debug, Clone, PartialEq, Eq)]
pub enum UpdateAvailability {
    Absent,
    Newer(String),
    Updating(String),
    Installed(String),
    Failed { version: String, reason: String },
}
