use uuid::Uuid;

use crate::domain::workspace_id::WorkspaceId;
use crate::domain::workspace_ids::WorkspaceIds;

pub struct RandomWorkspaceIds;

impl WorkspaceIds for RandomWorkspaceIds {
    fn next(&mut self) -> WorkspaceId {
        loop {
            if let Ok(id) = WorkspaceId::parse(&Uuid::new_v4().to_string()) {
                return id;
            }
        }
    }
}
