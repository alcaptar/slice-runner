use crate::domain::liveness::Liveness;

pub trait ProcessProbe {
    fn liveness_of(&self, pid: u32) -> Liveness;
}
