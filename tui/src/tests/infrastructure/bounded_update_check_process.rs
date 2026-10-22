mod the_bounded_update_check_process {
    use std::sync::Arc;
    use std::time::Duration;

    use crate::domain::update_availability::UpdateAvailability;
    use crate::domain::update_check::UpdateCheck;
    use crate::infrastructure::bounded_update_check_process::BoundedUpdateCheckProcess;
    use crate::infrastructure::child_launcher::{ChildExit, Input, Launch, Stream};
    use crate::tests::doubles::{AdvancingClock, ChildCall, ChildCalls, ScriptedChildLauncher};

    const BUDGET: Duration = Duration::from_millis(100);
    const STEP: Duration = Duration::from_millis(40);

    struct Subject;

    impl Subject {
        fn over(launcher: ScriptedChildLauncher) -> BoundedUpdateCheckProcess {
            BoundedUpdateCheckProcess::new(
                vec!["slice-runner".to_string()],
                Arc::new(launcher),
                AdvancingClock::stepping(STEP),
                BUDGET,
            )
        }

        fn printing(exit: ChildExit, stdout: &str) -> (BoundedUpdateCheckProcess, ChildCalls) {
            let (launcher, calls) = ScriptedChildLauncher::answering(exit, stdout, "");

            (Self::over(launcher), calls)
        }
    }

    #[test]
    fn a_version_followed_by_a_newline_is_the_newer_version() {
        let (mut process, _calls) = Subject::printing(ChildExit::Code(0), "0.2.0\n");

        assert_eq!(process.availability(), UpdateAvailability::Newer("0.2.0".to_string()));
    }

    #[test]
    fn asks_slice_runner_update_with_check_and_reads_only_the_standard_output() {
        let (mut process, calls) = Subject::printing(ChildExit::Code(0), "");

        process.availability();

        assert_eq!(
            calls.lock().unwrap()[0],
            ChildCall::Launched {
                argv: vec!["slice-runner".to_string(), "update".to_string(), "--check".to_string()],
                launch: Launch::new(Input::Empty, Stream::Read, Stream::Discard),
            }
        );
    }

    #[test]
    fn an_empty_output_announces_nothing() {
        let (mut process, _calls) = Subject::printing(ChildExit::Code(0), "");

        assert_eq!(process.availability(), UpdateAvailability::Absent);
    }

    #[test]
    fn an_output_that_is_not_exactly_a_version_and_a_newline_announces_nothing() {
        for output in ["0.2.0", "\n", "v 0.2.0\n", "0.2.0\n0.3.0\n"] {
            let (mut process, _calls) = Subject::printing(ChildExit::Code(0), output);

            assert_eq!(process.availability(), UpdateAvailability::Absent, "{output:?}");
        }
    }

    #[test]
    fn a_failing_command_announces_nothing_even_if_it_printed_a_version() {
        let (mut process, _calls) = Subject::printing(ChildExit::Code(1), "0.2.0\n");

        assert_eq!(process.availability(), UpdateAvailability::Absent);
    }

    #[test]
    fn a_program_that_cannot_be_launched_announces_nothing() {
        let (launcher, _calls) = ScriptedChildLauncher::unlaunchable("no such file");
        let mut process = Subject::over(launcher);

        assert_eq!(process.availability(), UpdateAvailability::Absent);
    }

    #[test]
    fn a_check_that_never_ends_is_killed_and_waited_at_the_budget_and_announces_nothing() {
        let (launcher, calls) = ScriptedChildLauncher::never_ending();
        let mut process = Subject::over(launcher);

        let availability = process.availability();

        assert_eq!(availability, UpdateAvailability::Absent);
        assert_eq!(
            calls.lock().unwrap().iter().skip(1).cloned().collect::<Vec<_>>(),
            [ChildCall::Killed, ChildCall::Waited]
        );
    }
}
