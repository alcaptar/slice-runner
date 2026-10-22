#[derive(Debug, Clone, Copy, PartialEq, Eq, PartialOrd, Ord)]
pub enum Attention {
    NeedsYou,
    Running,
    Pending,
    Finished,
}

impl Attention {
    pub const ALL: [Self; 4] = [Self::NeedsYou, Self::Running, Self::Pending, Self::Finished];

    pub fn heading(self) -> &'static str {
        match self {
            Self::NeedsYou => "TE NECESITA",
            Self::Running => "EN MARCHA",
            Self::Pending => "PENDIENTES",
            Self::Finished => "TERMINADAS",
        }
    }
}
