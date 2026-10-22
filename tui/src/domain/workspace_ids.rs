use crate::domain::workspace_id::WorkspaceId;

pub trait WorkspaceIds {
    fn next(&mut self) -> WorkspaceId;
}
