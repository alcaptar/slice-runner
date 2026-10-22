#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum Counter {
    Controls,
    Hygiene,
    Judge,
    Ci,
    CiIndeterminate,
    CatchUp,
}

impl Counter {
    pub const ALL: [Self; 6] = [
        Self::Controls,
        Self::Hygiene,
        Self::Judge,
        Self::Ci,
        Self::CiIndeterminate,
        Self::CatchUp,
    ];

    pub fn label(self) -> &'static str {
        match self {
            Self::Controls => "controles",
            Self::Hygiene => "higiene",
            Self::Judge => "juez",
            Self::Ci => "ci",
            Self::CiIndeterminate => "ci indeterminada",
            Self::CatchUp => "puesta al día",
        }
    }

    pub fn sends_the_work_back(self) -> bool {
        match self {
            Self::Controls | Self::Hygiene | Self::Judge | Self::Ci => true,
            Self::CiIndeterminate | Self::CatchUp => false,
        }
    }
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub struct Round {
    used: u64,
    limit: u64,
}

impl Round {
    pub fn new(used: u64, limit: u64) -> Self {
        Self { used, limit }
    }

    pub fn used(self) -> u64 {
        self.used
    }

    pub fn limit(self) -> u64 {
        self.limit
    }

    pub fn is_spent(self) -> bool {
        self.used >= self.limit
    }
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub struct Rounds {
    controls: Round,
    hygiene: Round,
    judge: Round,
    ci: Round,
    ci_indeterminate: Round,
    catch_up: Round,
}

impl Rounds {
    pub fn new(
        controls: Round,
        hygiene: Round,
        judge: Round,
        ci: Round,
        ci_indeterminate: Round,
        catch_up: Round,
    ) -> Self {
        Self {
            controls,
            hygiene,
            judge,
            ci,
            ci_indeterminate,
            catch_up,
        }
    }

    pub fn of(&self, counter: Counter) -> Round {
        match counter {
            Counter::Controls => self.controls,
            Counter::Hygiene => self.hygiene,
            Counter::Judge => self.judge,
            Counter::Ci => self.ci,
            Counter::CiIndeterminate => self.ci_indeterminate,
            Counter::CatchUp => self.catch_up,
        }
    }

    pub fn implementation_round(&self) -> u64 {
        Counter::ALL
            .into_iter()
            .filter(|counter| counter.sends_the_work_back())
            .map(|counter| self.of(counter).used())
            .sum::<u64>()
            + 1
    }

    pub fn grown_since(&self, earlier: &Self) -> Option<Counter> {
        Counter::ALL
            .into_iter()
            .find(|counter| self.of(*counter).used() > earlier.of(*counter).used())
    }

    pub fn in_use(&self) -> Vec<(Counter, Round)> {
        Counter::ALL
            .into_iter()
            .map(|counter| (counter, self.of(counter)))
            .filter(|(_, round)| round.used() > 0)
            .collect()
    }
}
