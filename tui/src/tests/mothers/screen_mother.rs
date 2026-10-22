use crate::domain::activity_line::{ActivityLine, Actor};
use crate::domain::closing_reason::ClosingReason;
use crate::domain::closure::Closure;
use crate::domain::follow_entry::FollowEntry;
use crate::domain::follow_line::FollowLine;
use crate::domain::parent::Parent;
use crate::domain::slice_key::SliceKey;
use crate::domain::slice_subject::SliceSubject;
use crate::domain::spend::Spend;
use crate::domain::step::Step;
use crate::domain::transition::Transition;
use crate::tests::mothers::follow_line_mother::FollowLineMother;

struct Moment {
    minutes_ago: u64,
    closure: Closure,
    step: Option<Step>,
    controls: u64,
    judge: u64,
    cost: f64,
}

pub struct ScreenMother;

impl ScreenMother {
    pub const NOW: u64 = 1_792_154_490_000;
    pub const PARENT: u64 = 525;
    const MINUTE: u64 = 60_000;
    const SECOND: u64 = 1_000;
    const NAMES: [&'static str; 6] = [
        "las-decisiones-viajan-en-la-spec",
        "las-decisiones-sustituyen-al-entendimiento",
        "el-juez-mide-contra-las-decisiones",
        "la-vista-de-detalle-sin-entendimiento",
        "adios-al-entendimiento",
        "el-diseno-se-decide-en-slice-spec",
    ];
    pub const JUDGED_PID: u32 = 4242;
    pub const IMPLEMENTED_PID: u32 = 4243;

    pub fn key(slice: u64) -> SliceKey {
        SliceKey::new(FollowLineMother::REPO, Self::PARENT + slice)
    }

    pub fn feature() -> Vec<FollowEntry> {
        let in_progress = Closure::InProgress;
        let mut entries = Vec::new();
        entries.extend(Self::slice(
            1,
            Some(4240),
            None,
            &[
                Self::moment(200, in_progress, Some(Step::Implement), (0, 0), 0.0),
                Self::moment(192, Closure::AwaitingMerge, Some(Step::AwaitMerge), (0, 0), 2.7),
            ],
        ));
        entries.extend(Self::slice(
            4,
            Some(4241),
            None,
            &[
                Self::moment(59, in_progress, Some(Step::Implement), (0, 0), 0.0),
                Self::moment(51, in_progress, Some(Step::RunControls), (0, 0), 1.2),
                Self::moment(49, in_progress, Some(Step::Implement), (1, 0), 1.3),
                Self::moment(43, in_progress, Some(Step::RunControls), (1, 0), 3.0),
                Self::moment(
                    41,
                    Closure::Blocked(ClosingReason::Controls),
                    Some(Step::RunControls),
                    (2, 0),
                    3.1,
                ),
            ],
        ));
        entries.extend(Self::slice(
            2,
            Some(Self::JUDGED_PID),
            None,
            &[
                Self::moment(23, in_progress, Some(Step::Implement), (0, 0), 0.0),
                Self::moment(15, in_progress, Some(Step::RunControls), (0, 0), 0.9),
                Self::moment(13, in_progress, Some(Step::Verify), (0, 0), 1.1),
                Self::moment(10, in_progress, Some(Step::Implement), (0, 1), 1.3),
                Self::moment(8, in_progress, Some(Step::RunControls), (0, 1), 1.7),
                Self::moment(6, in_progress, Some(Step::Verify), (0, 1), 1.84),
            ],
        ));
        entries.extend(Self::slice(
            3,
            Some(Self::IMPLEMENTED_PID),
            None,
            &[Self::moment(2, in_progress, Some(Step::Implement), (0, 0), 42.0)],
        ));
        entries.extend(Self::slice(
            5,
            None,
            None,
            &[Self::moment(300, Closure::Pending, None, (0, 0), 0.0)],
        ));
        entries.extend(Self::slice(
            6,
            Some(4239),
            Some(541),
            &[Self::moment(1500, Closure::Merged, Some(Step::AwaitMerge), (0, 0), 6.2)],
        ));
        entries
    }

    pub fn feature_with_activity() -> Vec<FollowEntry> {
        let mut entries = Self::feature();
        entries.extend([
            Self::activity(2, 39, Actor::Judge, "Read", "docs/conventions/domain.md"),
            Self::activity(
                2,
                32,
                Actor::Judge,
                "Read",
                "src/slice_runner/domain/precheck_outcome.py",
            ),
            Self::activity(2, 28, Actor::Judge, "Read", "src/slice_runner/domain/sub_issue.py"),
            Self::activity(2, 21, Actor::Judge, "Grep", "MISSING_DECISIONS src/"),
            Self::activity(2, 15, Actor::Judge, "Bash", "git diff --stat origin/master"),
            Self::activity(
                2,
                8,
                Actor::Judge,
                "Read",
                "src/slice_runner/tests/mothers/sub_issue_mother.py",
            ),
            Self::activity(
                3,
                140,
                Actor::Implementer,
                "Edit",
                "src/slice_runner/infrastructure/slice_verifier_judge.py",
            ),
        ]);
        entries
    }

    fn moment(minutes_ago: u64, closure: Closure, step: Option<Step>, rounds: (u64, u64), cost: f64) -> Moment {
        Moment {
            minutes_ago,
            closure,
            step,
            controls: rounds.0,
            judge: rounds.1,
            cost,
        }
    }

    fn slice(number: u64, pid: Option<u32>, merged_pull_request: Option<u64>, moments: &[Moment]) -> Vec<FollowEntry> {
        let subject = Self::subject_of(number);

        moments
            .iter()
            .map(|moment| {
                let mut transition = Transition::new(
                    Self::NOW - moment.minutes_ago * Self::MINUTE,
                    moment.closure,
                    moment.step,
                    FollowLineMother::rounds(moment.controls, moment.judge),
                    Spend::new(moment.cost, 50.0),
                );
                if moment.closure == Closure::AwaitingMerge {
                    transition = transition.with_pull_request(544);
                }
                if let Some(number) = merged_pull_request {
                    transition = transition.with_pull_request(number);
                }
                if let Some(pid) = pid {
                    transition = transition.with_pid(pid);
                }
                FollowEntry::Transition(FollowLine::new(subject.clone(), transition))
            })
            .collect()
    }

    fn activity(number: u64, seconds_ago: u64, actor: Actor, tool: &str, target: &str) -> FollowEntry {
        FollowEntry::Activity(ActivityLine::new(
            Self::key(number),
            Self::NOW - seconds_ago * Self::SECOND,
            actor,
            tool,
            target,
        ))
    }

    pub fn spending(cost: f64) -> FollowLine {
        FollowLine::new(
            Self::subject_of(3),
            Transition::new(
                Self::NOW,
                Closure::InProgress,
                Some(Step::Implement),
                FollowLineMother::rounds(0, 0),
                Spend::new(cost, 50.0),
            ),
        )
    }

    pub fn slice_spending(number: u64, cost: f64) -> FollowLine {
        FollowLine::new(
            Self::subject_of(number),
            Transition::new(
                Self::NOW,
                Closure::InProgress,
                Some(Step::Implement),
                FollowLineMother::rounds(0, 0),
                Spend::new(cost, 50.0),
            ),
        )
    }

    pub fn a_round_without_changes() -> Vec<FollowLine> {
        let implementing = |minutes_ago: u64| {
            Transition::new(
                Self::NOW - minutes_ago * Self::MINUTE,
                Closure::InProgress,
                Some(Step::Implement),
                FollowLineMother::rounds(0, 0),
                Spend::new(0.0, 50.0),
            )
        };

        vec![
            FollowLine::new(Self::subject_of(7), implementing(9)),
            FollowLine::new(Self::subject_of(7), implementing(4).without_changes()),
        ]
    }

    fn subject_of(number: u64) -> SliceSubject {
        SliceSubject::new(
            FollowLineMother::REPO,
            Self::PARENT + number,
            &format!("slice-0{number}"),
            Parent::Issue(Self::PARENT),
            usize::try_from(number - 1)
                .ok()
                .and_then(|index| Self::NAMES.get(index))
                .copied(),
        )
    }

    pub fn a_long_blocked_story() -> Vec<FollowLine> {
        let mut lines: Vec<FollowLine> = (0..10)
            .map(|round| {
                let step = if round % 2 == 0 {
                    Step::Implement
                } else {
                    Step::RunControls
                };
                FollowLine::new(
                    Self::subject_of(8),
                    Transition::new(
                        Self::NOW - (40 - round * 3) * Self::MINUTE,
                        Closure::InProgress,
                        Some(step),
                        FollowLineMother::rounds(round / 2, 0),
                        Spend::new(1.0, 50.0),
                    ),
                )
            })
            .collect();
        lines.push(FollowLine::new(
            Self::subject_of(8),
            Transition::new(
                Self::NOW - Self::MINUTE,
                Closure::Blocked(ClosingReason::Controls),
                Some(Step::RunControls),
                FollowLineMother::rounds(2, 0),
                Spend::new(1.0, 50.0),
            ),
        ));
        lines
    }

    pub fn reopened_without_a_process() -> Vec<FollowEntry> {
        let mut entries: Vec<FollowEntry> = Self::feature()
            .into_iter()
            .filter(|entry| matches!(entry, FollowEntry::Transition(line) if line.issue() == Self::PARENT + 4))
            .collect();
        entries.push(FollowEntry::Transition(FollowLine::new(
            Self::subject_of(4),
            Transition::new(
                Self::NOW,
                Closure::InProgress,
                Some(Step::Implement),
                FollowLineMother::rounds(0, 0),
                Spend::new(3.1, 50.0),
            ),
        )));
        entries
    }

    pub fn the_same_step_twice_with_more_spend() -> (FollowLine, FollowLine) {
        let implementing = |minutes_ago: u64, cost: f64| {
            FollowLine::new(
                Self::subject_of(3),
                Transition::new(
                    Self::NOW - minutes_ago * Self::MINUTE,
                    Closure::InProgress,
                    Some(Step::Implement),
                    FollowLineMother::rounds(0, 0),
                    Spend::new(cost, 50.0),
                ),
            )
        };

        (implementing(9, 30.0), implementing(2, 45.0))
    }
}
