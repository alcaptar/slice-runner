use std::sync::mpsc::{self, Receiver};
use std::thread;

use crate::domain::update_availability::UpdateAvailability;
use crate::domain::update_check::UpdateCheck;

pub struct ThreadedUpdateCheck {
    answers: Receiver<UpdateAvailability>,
    last: UpdateAvailability,
}

impl ThreadedUpdateCheck {
    pub fn start<C: UpdateCheck + Send + 'static>(mut check: C) -> Self {
        let (sender, answers) = mpsc::channel();
        thread::spawn(move || {
            sender.send(check.availability()).ok();
        });

        Self {
            answers,
            last: UpdateAvailability::Absent,
        }
    }

    pub fn latest(&mut self) -> UpdateAvailability {
        if let Some(answer) = self.answers.try_iter().last() {
            self.last = answer;
        }

        self.last.clone()
    }
}

impl UpdateCheck for ThreadedUpdateCheck {
    fn availability(&mut self) -> UpdateAvailability {
        self.latest()
    }
}
