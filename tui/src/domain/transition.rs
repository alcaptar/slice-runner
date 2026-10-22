use crate::domain::closure::Closure;
use crate::domain::rounds::Rounds;
use crate::domain::spend::Spend;
use crate::domain::step::Step;

#[derive(Debug, Clone, PartialEq)]
pub struct Transition {
    at: u64,
    closure: Closure,
    step: Option<Step>,
    rounds: Rounds,
    spend: Spend,
    round_without_changes: bool,
    pull_request: Option<u64>,
    comparison: Option<String>,
    pid: Option<u32>,
}

impl Transition {
    pub fn new(at: u64, closure: Closure, step: Option<Step>, rounds: Rounds, spend: Spend) -> Self {
        Self {
            at,
            closure,
            step,
            rounds,
            spend,
            round_without_changes: false,
            pull_request: None,
            comparison: None,
            pid: None,
        }
    }

    pub fn without_changes(self) -> Self {
        Self {
            round_without_changes: true,
            ..self
        }
    }

    pub fn with_pull_request(self, number: u64) -> Self {
        Self {
            pull_request: Some(number),
            ..self
        }
    }

    pub fn with_comparison(self, path: &str) -> Self {
        Self {
            comparison: Some(path.to_string()),
            ..self
        }
    }

    pub fn with_pid(self, pid: u32) -> Self {
        Self { pid: Some(pid), ..self }
    }

    pub fn since(self, at: u64) -> Self {
        Self { at, ..self }
    }

    pub fn at(&self) -> u64 {
        self.at
    }

    pub fn closure(&self) -> Closure {
        self.closure
    }

    pub fn step(&self) -> Option<Step> {
        self.step
    }

    pub fn rounds(&self) -> &Rounds {
        &self.rounds
    }

    pub fn spend(&self) -> Spend {
        self.spend
    }

    pub fn round_without_changes(&self) -> bool {
        self.round_without_changes
    }

    pub fn pull_request(&self) -> Option<u64> {
        self.pull_request
    }

    pub fn comparison(&self) -> Option<&str> {
        self.comparison.as_deref()
    }

    pub fn pid(&self) -> Option<u32> {
        self.pid
    }

    pub fn repeats(&self, earlier: &Self) -> bool {
        self.closure == earlier.closure
            && self.step == earlier.step
            && self.rounds == earlier.rounds
            && self.round_without_changes == earlier.round_without_changes
            && self.pull_request == earlier.pull_request
            && self.comparison == earlier.comparison
    }
}
