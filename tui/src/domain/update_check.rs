use crate::domain::update_availability::UpdateAvailability;

pub trait UpdateCheck {
    fn availability(&mut self) -> UpdateAvailability;
}
