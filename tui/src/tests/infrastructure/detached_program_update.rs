mod the_detached_program_update {
    use std::path::PathBuf;
    use std::sync::Arc;
    use std::time::Duration;

    use uuid::Uuid;

    use crate::domain::clock::Clock;
    use crate::domain::program_update::ProgramUpdate;
    use crate::domain::update_progress::UpdateProgress;
    use crate::infrastructure::child_launcher::{ChildExit, Input, Stream};
    use crate::infrastructure::detached_program_update::DetachedProgramUpdate;
    use crate::tests::doubles::{AdvancingClock, ChildCall, ChildCalls, ScriptedChildLauncher, SteppedClock};
    use crate::tests::waiting::Waiting;

    const BUDGET: Duration = Duration::from_secs(1);
    const STEP: Duration = Duration::from_millis(400);

    struct Scratch {
        directory: PathBuf,
    }

    impl Scratch {
        fn new() -> Self {
            let directory = std::env::temp_dir().join(format!("detached-update-{}", Uuid::new_v4()));
            std::fs::create_dir_all(&directory).unwrap();

            Self { directory }
        }

        fn update_over(&self, launcher: ScriptedChildLauncher) -> DetachedProgramUpdate {
            self.update_timed_by(launcher, AdvancingClock::stepping(STEP))
        }

        fn update_timed_by(
            &self,
            launcher: ScriptedChildLauncher,
            clock: impl Clock + 'static,
        ) -> DetachedProgramUpdate {
            DetachedProgramUpdate::new(
                vec!["slice-runner".to_string()],
                Arc::new(launcher),
                clock,
                BUDGET,
                self.directory.clone(),
            )
        }

        fn answering(&self, exit: ChildExit, stderr: &str) -> (DetachedProgramUpdate, ChildCalls) {
            let (launcher, calls) = ScriptedChildLauncher::answering(exit, "", stderr);

            (self.update_over(launcher), calls)
        }

        fn leftovers(&self) -> usize {
            std::fs::read_dir(&self.directory).unwrap().count()
        }

        fn finished(update: &mut DetachedProgramUpdate) -> UpdateProgress {
            Waiting::until(|| Some(update.progress()).filter(|progress| *progress != UpdateProgress::Running))
        }
    }

    impl Drop for Scratch {
        fn drop(&mut self) {
            std::fs::remove_dir_all(&self.directory).ok();
        }
    }

    #[test]
    fn a_child_that_exits_with_zero_is_installed() {
        let scratch = Scratch::new();
        let (mut update, _calls) = scratch.answering(ChildExit::Code(0), "");

        update.start("0.4.0");

        assert_eq!(Scratch::finished(&mut update), UpdateProgress::Installed);
    }

    #[test]
    fn the_child_is_launched_as_slice_runner_update_with_an_empty_input_discarding_the_output_and_sending_the_errors_to_a_file()
     {
        let scratch = Scratch::new();
        let (mut update, calls) = scratch.answering(ChildExit::Code(0), "");

        update.start("0.4.0");
        Scratch::finished(&mut update);

        let ChildCall::Launched { argv, launch } = calls.lock().unwrap()[0].clone() else {
            unreachable!("the first call is the launch");
        };
        assert_eq!(argv, ["slice-runner", "update"]);
        assert_eq!(launch.stdin(), Input::Empty);
        assert_eq!(launch.stdout(), &Stream::Discard);
        assert!(
            matches!(launch.stderr(), Stream::File(path) if path.parent() == Some(scratch.directory.as_path())),
            "{:?}",
            launch.stderr()
        );
    }

    #[test]
    fn while_the_child_runs_the_progress_is_running() {
        let scratch = Scratch::new();
        let clock = SteppedClock::standing_still();
        let (launcher, _calls) = ScriptedChildLauncher::never_ending();
        let mut update = scratch.update_timed_by(launcher, clock.clone());

        update.start("0.4.0");

        assert_eq!(update.progress(), UpdateProgress::Running);
        Waiting::until(|| {
            clock.advance(BUDGET);
            Some(update.progress()).filter(|progress| *progress != UpdateProgress::Running)
        });
    }

    #[test]
    fn the_reason_is_the_last_non_empty_line_of_the_error_output() {
        let scratch = Scratch::new();
        let (mut update, _calls) = scratch.answering(ChildExit::Code(3), "first\nthe last line\n\n  \n");

        update.start("0.4.0");

        assert_eq!(
            Scratch::finished(&mut update),
            UpdateProgress::Failed("the last line".to_string())
        );
    }

    #[test]
    fn a_child_that_wrote_nothing_fails_with_its_exit_code() {
        let scratch = Scratch::new();
        let (mut update, _calls) = scratch.answering(ChildExit::Code(3), "");

        update.start("0.4.0");

        assert_eq!(
            Scratch::finished(&mut update),
            UpdateProgress::Failed("salio con 3".to_string())
        );
    }

    #[test]
    fn a_program_that_cannot_be_launched_fails_carrying_why() {
        let scratch = Scratch::new();
        let (launcher, _calls) = ScriptedChildLauncher::unlaunchable("no such file");
        let mut update = scratch.update_over(launcher);

        update.start("0.4.0");

        assert_eq!(
            Scratch::finished(&mut update),
            UpdateProgress::Failed("no such file".to_string())
        );
    }

    #[test]
    fn a_child_that_outlives_the_budget_is_killed_and_waited_and_the_reason_names_the_budget() {
        let scratch = Scratch::new();
        let (launcher, calls) = ScriptedChildLauncher::never_ending();
        let mut update = scratch.update_over(launcher);

        update.start("0.4.0");
        let progress = Scratch::finished(&mut update);

        assert_eq!(progress, UpdateProgress::Failed("no termino en 1 s".to_string()));
        assert_eq!(
            calls.lock().unwrap().iter().skip(1).cloned().collect::<Vec<_>>(),
            [ChildCall::Killed, ChildCall::Waited]
        );
    }

    #[test]
    fn the_child_is_not_killed_when_the_adapter_is_released_before_it_finishes() {
        let scratch = Scratch::new();
        let (launcher, calls, gate) = ScriptedChildLauncher::finishing_once_released(ChildExit::Code(0));
        let mut update = scratch.update_timed_by(launcher, SteppedClock::standing_still());
        update.start("0.4.0");

        drop(update);
        gate.open();

        Waiting::until(|| calls.lock().unwrap().contains(&ChildCall::Exited).then_some(()));
        assert!(!calls.lock().unwrap().contains(&ChildCall::Killed));
    }

    #[test]
    fn reading_the_result_deletes_the_error_file() {
        let scratch = Scratch::new();
        let (mut update, _calls) = scratch.answering(ChildExit::Code(1), "bad\n");
        update.start("0.4.0");
        Waiting::until(|| (scratch.leftovers() == 1).then_some(()));

        let progress = Scratch::finished(&mut update);

        assert_eq!(progress, UpdateProgress::Failed("bad".to_string()));
        assert_eq!(scratch.leftovers(), 0);
    }
}
