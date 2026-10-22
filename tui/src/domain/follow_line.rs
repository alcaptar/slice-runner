use crate::domain::slice_subject::SliceSubject;
use crate::domain::transition::Transition;

#[derive(Debug, Clone, PartialEq)]
pub struct FollowLine {
    subject: SliceSubject,
    transition: Transition,
}

impl FollowLine {
    pub fn new(subject: SliceSubject, transition: Transition) -> Self {
        Self { subject, transition }
    }

    pub fn repo(&self) -> &str {
        self.subject.repo()
    }

    pub fn issue(&self) -> u64 {
        self.subject.issue()
    }

    pub fn into_parts(self) -> (SliceSubject, Transition) {
        (self.subject, self.transition)
    }
}
