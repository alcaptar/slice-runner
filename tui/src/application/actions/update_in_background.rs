use crate::domain::auto_update::AutoUpdate;
use crate::domain::program_update::ProgramUpdate;
use crate::domain::update_availability::UpdateAvailability;
use crate::domain::update_check::UpdateCheck;
use crate::domain::update_progress::UpdateProgress;

pub struct UpdateInBackground<C: UpdateCheck, U: ProgramUpdate> {
    check: C,
    update: U,
    auto_update: AutoUpdate,
    started: Option<String>,
    settled: Option<UpdateAvailability>,
}

impl<C: UpdateCheck, U: ProgramUpdate> UpdateInBackground<C, U> {
    pub fn new(check: C, update: U, auto_update: AutoUpdate) -> Self {
        Self {
            check,
            update,
            auto_update,
            started: None,
            settled: None,
        }
    }

    pub fn execute(&mut self) -> UpdateAvailability {
        if let Some(settled) = &self.settled {
            return settled.clone();
        }

        match self.started.clone() {
            Some(version) => self.followed(version),
            None => self.checked(),
        }
    }

    fn checked(&mut self) -> UpdateAvailability {
        let answer = self.check.availability();
        match (&answer, self.auto_update) {
            (UpdateAvailability::Newer(version), AutoUpdate::Enabled) => {
                let version = version.clone();
                self.update.start(&version);
                self.started = Some(version.clone());

                UpdateAvailability::Updating(version)
            }
            (_, AutoUpdate::Enabled | AutoUpdate::Disabled) => answer,
        }
    }

    fn followed(&mut self, version: String) -> UpdateAvailability {
        let outcome = match self.update.progress() {
            UpdateProgress::Running => return UpdateAvailability::Updating(version),
            UpdateProgress::Installed => UpdateAvailability::Installed(version),
            UpdateProgress::Failed(reason) => UpdateAvailability::Failed { version, reason },
        };
        self.settled = Some(outcome.clone());

        outcome
    }
}
