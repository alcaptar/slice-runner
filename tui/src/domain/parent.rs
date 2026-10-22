#[derive(Debug, Clone, Copy, PartialEq, Eq, PartialOrd, Ord)]
pub enum Parent {
    Issue(u64),
    Absent,
}

impl Parent {
    pub fn or_known(self, earlier: Self) -> Self {
        match self {
            Self::Issue(_) => self,
            Self::Absent => earlier,
        }
    }
}
