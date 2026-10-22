use crate::domain::errors::ComparisonNotOpened;

pub trait ComparisonOpener: Send {
    fn open(&mut self, path: &str) -> Result<(), ComparisonNotOpened>;
}
