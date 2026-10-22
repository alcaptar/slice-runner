#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum Liveness {
    Unchecked,
    Alive,
    Gone,
}
