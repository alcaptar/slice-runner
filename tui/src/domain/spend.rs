#[derive(Debug, Clone, Copy, PartialEq)]
pub struct Spend {
    cost_usd: f64,
    budget_usd: f64,
}

impl Spend {
    const WARNING_SHARE: f64 = 0.8;

    pub fn new(cost_usd: f64, budget_usd: f64) -> Self {
        Self { cost_usd, budget_usd }
    }

    pub fn cost_usd(self) -> f64 {
        self.cost_usd
    }

    pub fn budget_usd(self) -> f64 {
        self.budget_usd
    }

    pub fn nears_the_budget(self) -> bool {
        self.cost_usd >= self.budget_usd * Self::WARNING_SHARE
    }
}
