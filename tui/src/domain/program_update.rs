use crate::domain::update_progress::UpdateProgress;

pub trait ProgramUpdate {
    fn start(&mut self, version: &str);
    fn progress(&mut self) -> UpdateProgress;
}
