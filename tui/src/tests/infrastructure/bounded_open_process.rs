mod the_bounded_open_process {
    use std::sync::Arc;
    use std::time::Duration;

    use crate::domain::comparison_opener::ComparisonOpener;
    use crate::domain::errors::ComparisonNotOpened;
    use crate::infrastructure::bounded_open_process::BoundedOpenProcess;
    use crate::infrastructure::child_launcher::{ChildExit, Input, Launch, Stream};
    use crate::tests::doubles::{AdvancingClock, ChildCall, ChildCalls, ScriptedChildLauncher};

    const BUDGET: Duration = Duration::from_millis(100);
    const STEP: Duration = Duration::from_millis(40);

    struct Subject;

    impl Subject {
        fn over(launcher: ScriptedChildLauncher) -> BoundedOpenProcess {
            BoundedOpenProcess::new(
                vec!["open".to_string()],
                Arc::new(launcher),
                AdvancingClock::stepping(STEP),
                BUDGET,
            )
        }

        fn answering(exit: ChildExit, stderr: &str) -> (BoundedOpenProcess, ChildCalls) {
            let (launcher, calls) = ScriptedChildLauncher::answering(exit, "", stderr);

            (Self::over(launcher), calls)
        }
    }

    #[test]
    fn hands_the_path_to_the_program_as_its_only_argument_and_reads_only_the_standard_error() {
        let (mut process, calls) = Subject::answering(ChildExit::Code(0), "");

        process.open("/work/comparison.html").ok();

        assert_eq!(
            calls.lock().unwrap()[0],
            ChildCall::Launched {
                argv: vec!["open".to_string(), "/work/comparison.html".to_string()],
                launch: Launch::new(Input::Empty, Stream::Discard, Stream::Read),
            }
        );
    }

    #[test]
    fn a_zero_exit_is_opened() {
        let (mut process, _calls) = Subject::answering(ChildExit::Code(0), "");

        assert_eq!(process.open("/work/comparison.html"), Ok(()));
    }

    #[test]
    fn a_non_zero_exit_is_a_failed_command_carrying_the_standard_error() {
        let (mut process, _calls) = Subject::answering(ChildExit::Code(1), "no application knows how to open it\n");

        assert_eq!(
            process.open("/work/comparison.html"),
            Err(ComparisonNotOpened::CommandFailed {
                reason: "no application knows how to open it".to_string()
            })
        );
    }

    #[test]
    fn a_non_zero_exit_without_standard_error_names_the_code() {
        let (mut process, _calls) = Subject::answering(ChildExit::Code(3), "");

        assert_eq!(
            process.open("/work/comparison.html"),
            Err(ComparisonNotOpened::CommandFailed {
                reason: "exited with code 3".to_string()
            })
        );
    }

    #[test]
    fn a_program_that_never_ends_is_killed_and_waited_at_the_budget() {
        let (launcher, calls) = ScriptedChildLauncher::never_ending();
        let mut process = Subject::over(launcher);

        let outcome = process.open("/work/comparison.html");

        assert_eq!(outcome, Err(ComparisonNotOpened::TimedOut { budget: BUDGET }));
        assert_eq!(
            calls.lock().unwrap().iter().skip(1).cloned().collect::<Vec<_>>(),
            [ChildCall::Killed, ChildCall::Waited]
        );
    }

    #[test]
    fn a_program_that_cannot_be_launched_is_a_failed_command_carrying_why() {
        let (launcher, _calls) = ScriptedChildLauncher::unlaunchable("no such file");
        let mut process = Subject::over(launcher);

        assert_eq!(
            process.open("/work/comparison.html"),
            Err(ComparisonNotOpened::CommandFailed {
                reason: "no such file".to_string()
            })
        );
    }
}
