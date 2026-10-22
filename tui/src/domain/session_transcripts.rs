use std::path::Path;

use crate::domain::workspace_id::WorkspaceId;

pub trait SessionTranscripts {
    fn exists(&self, directory: &Path, id: &WorkspaceId) -> bool;
}
