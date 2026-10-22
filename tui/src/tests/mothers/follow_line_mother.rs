use crate::domain::closure::Closure;
use crate::domain::follow_line::FollowLine;
use crate::domain::parent::Parent;
use crate::domain::rounds::{Round, Rounds};
use crate::domain::slice_subject::SliceSubject;
use crate::domain::spend::Spend;
use crate::domain::step::Step;
use crate::domain::transition::Transition;

pub struct FollowLineMother;

impl FollowLineMother {
    pub const REPO: &'static str = "alcaptar/demo-workspace";
    pub const NAME: &'static str = "follow-speaks-json";
    pub const COMPARISON: &'static str = "/work/.design-captures/comparison.html";

    pub fn rounds(controls: u64, judge: u64) -> Rounds {
        Rounds::new(
            Round::new(controls, 2),
            Round::new(0, 2),
            Round::new(judge, 2),
            Round::new(0, 1),
            Round::new(0, 10),
            Round::new(0, 3),
        )
    }

    pub fn working_at(step: Step) -> Transition {
        Transition::new(
            0,
            Closure::InProgress,
            Some(step),
            Self::rounds(0, 0),
            Spend::new(0.0, 50.0),
        )
    }

    pub fn child_of(parent: u64, issue: u64) -> FollowLine {
        Self::child_of_in_repo(Self::REPO, parent, issue)
    }

    pub fn child_of_in_repo(repo: &str, parent: u64, issue: u64) -> FollowLine {
        FollowLine::new(
            SliceSubject::new(repo, issue, "slice-01", Parent::Issue(parent), Some(Self::NAME)),
            Self::working_at(Step::RunControls),
        )
    }

    pub fn orphan(issue: u64) -> FollowLine {
        FollowLine::new(
            SliceSubject::new(Self::REPO, issue, "slice-02", Parent::Absent, None),
            Self::working_at(Step::Implement),
        )
    }

    pub fn merged(earlier: &FollowLine) -> FollowLine {
        Self::with_subject_of(
            earlier,
            Transition::new(
                0,
                Closure::Merged,
                Some(Step::AwaitMerge),
                Self::rounds(0, 0),
                Spend::new(0.0, 50.0),
            ),
        )
    }

    pub fn merged_without_parent_or_name(earlier: &FollowLine) -> FollowLine {
        FollowLine::new(
            SliceSubject::new(earlier.repo(), earlier.issue(), "slice-01", Parent::Absent, None),
            Transition::new(
                0,
                Closure::Merged,
                Some(Step::AwaitMerge),
                Self::rounds(0, 0),
                Spend::new(0.0, 50.0),
            ),
        )
    }

    pub fn awaiting_merge_with_comparison(earlier: &FollowLine) -> FollowLine {
        Self::with_subject_of(
            earlier,
            Transition::new(
                0,
                Closure::AwaitingMerge,
                Some(Step::AwaitMerge),
                Self::rounds(0, 0),
                Spend::new(0.0, 50.0),
            )
            .with_comparison(Self::COMPARISON),
        )
    }

    pub fn moved_to(earlier: &FollowLine, step: Step) -> FollowLine {
        Self::with_subject_of(earlier, Self::working_at(step))
    }

    fn with_subject_of(earlier: &FollowLine, transition: Transition) -> FollowLine {
        let (subject, _) = earlier.clone().into_parts();

        FollowLine::new(subject, transition)
    }
}
