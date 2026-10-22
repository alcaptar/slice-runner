use crate::domain::activity_line::ActivityLine;
use crate::domain::follow_line::FollowLine;

#[derive(Debug, Clone, PartialEq)]
pub enum FollowEntry {
    Transition(FollowLine),
    Activity(ActivityLine),
}
