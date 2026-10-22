use std::path::{Path, PathBuf};

use crate::domain::session_transcripts::SessionTranscripts;
use crate::domain::workspace_id::WorkspaceId;

pub struct ConfigDirSessionTranscripts {
    config: PathBuf,
}

impl ConfigDirSessionTranscripts {
    const PROJECTS: &'static str = "projects";
    const EXTENSION: &'static str = "jsonl";

    pub fn new(config: PathBuf) -> Self {
        Self { config }
    }

    fn folder_name(directory: &Path) -> String {
        directory.to_string_lossy().replace(['/', '.'], "-")
    }
}

impl SessionTranscripts for ConfigDirSessionTranscripts {
    fn exists(&self, directory: &Path, id: &WorkspaceId) -> bool {
        self.config
            .join(Self::PROJECTS)
            .join(Self::folder_name(directory))
            .join(format!("{}.{}", id.as_str(), Self::EXTENSION))
            .is_file()
    }
}
