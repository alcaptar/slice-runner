use crate::domain::errors::FollowLineRejected;
use crate::domain::follow_entry::FollowEntry;

pub trait FollowSource {
    fn pending(&mut self) -> Vec<Result<FollowEntry, FollowLineRejected>>;
}
