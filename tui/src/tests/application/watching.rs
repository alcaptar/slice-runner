use crate::application::queries::watch_slices::{WatchSlices, WatchedBoard};
use crate::domain::errors::FollowLineRejected;
use crate::domain::follow_entry::FollowEntry;
use crate::domain::follow_line::FollowLine;
use crate::domain::slice_board::SliceBoard;
use crate::domain::slice_key::SliceKey;
use crate::tests::doubles::{Delivery, FixedProbe, ScriptedFollowSource};
use crate::tests::mothers::follow_line_mother::FollowLineMother;

pub struct Watching;

impl Watching {
    pub fn one_tick(lines: Vec<Delivery>) -> WatchedBoard {
        let mut watch = WatchSlices::new(
            ScriptedFollowSource::delivering(vec![lines]),
            FixedProbe::everyone_alive(),
        );

        watch.execute(SliceBoard::empty())
    }

    pub fn lines(lines: Vec<FollowLine>) -> Vec<Delivery> {
        lines
            .into_iter()
            .map(|line| Ok(FollowEntry::Transition(line)))
            .collect()
    }

    pub fn wrong_issue() -> FollowLineRejected {
        FollowLineRejected::WrongValue {
            key: "issue".to_string(),
            reason: "expected a number".to_string(),
        }
    }

    pub fn key(issue: u64) -> SliceKey {
        SliceKey::new(FollowLineMother::REPO, issue)
    }

    pub fn three_slices_in_two_groups() -> WatchedBoard {
        Self::one_tick(Self::lines(vec![
            FollowLineMother::orphan(170),
            FollowLineMother::child_of(141, 160),
            FollowLineMother::child_of(140, 150),
        ]))
    }
}

impl Watching {
    pub fn entries(entries: Vec<FollowEntry>, probe: FixedProbe) -> WatchedBoard {
        let mut watch = WatchSlices::new(
            ScriptedFollowSource::delivering(vec![entries.into_iter().map(Ok).collect()]),
            probe,
        );

        watch.execute(SliceBoard::empty())
    }
}

impl Watching {
    pub fn awaiting_merge_with_comparison() -> WatchedBoard {
        let first = FollowLineMother::child_of(140, 150);

        Self::one_tick(Self::lines(vec![
            first.clone(),
            FollowLineMother::awaiting_merge_with_comparison(&first),
        ]))
    }
}
