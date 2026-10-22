mod the_bounded_gh_process {
    use std::sync::Arc;
    use std::time::Duration;

    use crate::domain::errors::IssuesUnread;
    use crate::domain::issue_source::IssueSource;
    use crate::domain::issue_text::IssueText;
    use crate::domain::open_issue::OpenIssue;
    use crate::infrastructure::bounded_gh_process::BoundedGhProcess;
    use crate::infrastructure::child_launcher::{ChildExit, Input, Launch, Stream};
    use crate::tests::doubles::{AdvancingClock, ChildCall, ChildCalls, ScriptedChildLauncher};

    const BUDGET: Duration = Duration::from_millis(100);
    const STEP: Duration = Duration::from_millis(40);

    struct Subject;

    impl Subject {
        fn over(launcher: ScriptedChildLauncher) -> BoundedGhProcess {
            BoundedGhProcess::new(
                vec!["gh".to_string()],
                Arc::new(launcher),
                AdvancingClock::stepping(STEP),
                BUDGET,
            )
        }

        fn answering(exit: ChildExit, stdout: &str, stderr: &str) -> (BoundedGhProcess, ChildCalls) {
            let (launcher, calls) = ScriptedChildLauncher::answering(exit, stdout, stderr);

            (Self::over(launcher), calls)
        }

        fn never_ending() -> (BoundedGhProcess, ChildCalls) {
            let (launcher, calls) = ScriptedChildLauncher::never_ending();

            (Self::over(launcher), calls)
        }

        fn launched(arguments: &[&str]) -> ChildCall {
            let mut argv = vec!["gh".to_string()];
            argv.extend(arguments.iter().map(ToString::to_string));

            ChildCall::Launched {
                argv,
                launch: Launch::new(Input::Empty, Stream::Read, Stream::Read),
            }
        }

        fn killed_then_waited(calls: &ChildCalls) -> Vec<ChildCall> {
            calls.lock().unwrap().iter().skip(1).cloned().collect()
        }
    }

    #[test]
    fn a_repo_view_that_never_ends_is_killed_and_waited_at_the_budget() {
        let (mut process, calls) = Subject::never_ending();

        let outcome = process.repo_of_directory();

        assert_eq!(outcome, Err(IssuesUnread::TimedOut { budget: BUDGET }));
        assert_eq!(
            Subject::killed_then_waited(&calls),
            [ChildCall::Killed, ChildCall::Waited]
        );
    }

    #[test]
    fn an_issue_list_that_never_ends_is_killed_and_waited_at_the_budget() {
        let (mut process, calls) = Subject::never_ending();

        let outcome = process.latest_open("alcaptar/demo-workspace", 20);

        assert_eq!(outcome, Err(IssuesUnread::TimedOut { budget: BUDGET }));
        assert_eq!(
            Subject::killed_then_waited(&calls),
            [ChildCall::Killed, ChildCall::Waited]
        );
    }

    #[test]
    fn an_issue_view_that_never_ends_is_killed_and_waited_at_the_budget() {
        let (mut process, calls) = Subject::never_ending();

        let outcome = process.body_of("alcaptar/demo-workspace", 516);

        assert_eq!(outcome, Err(IssuesUnread::TimedOut { budget: BUDGET }));
        assert_eq!(
            Subject::killed_then_waited(&calls),
            [ChildCall::Killed, ChildCall::Waited]
        );
    }

    #[test]
    fn asks_gh_for_the_name_with_owner_of_the_repo_of_the_directory() {
        let (mut process, calls) = Subject::answering(ChildExit::Code(1), "", "");

        process.repo_of_directory().ok();

        assert_eq!(
            calls.lock().unwrap()[0],
            Subject::launched(&["repo", "view", "--json", "nameWithOwner"])
        );
    }

    #[test]
    fn asks_gh_for_the_body_of_the_issue_in_the_repo() {
        let (mut process, calls) = Subject::answering(ChildExit::Code(1), "", "");

        process.body_of("alcaptar/demo-workspace", 516).ok();

        assert_eq!(
            calls.lock().unwrap()[0],
            Subject::launched(&[
                "issue",
                "view",
                "516",
                "--repo",
                "alcaptar/demo-workspace",
                "--json",
                "body,title"
            ])
        );
    }

    #[test]
    fn asks_gh_for_the_open_issues_of_the_repo_with_the_limit_and_the_fields_of_the_contract() {
        let (mut process, calls) = Subject::answering(ChildExit::Code(1), "", "");

        process.latest_open("alcaptar/demo-workspace", 20).ok();

        assert_eq!(
            calls.lock().unwrap()[0],
            Subject::launched(&[
                "issue",
                "list",
                "--repo",
                "alcaptar/demo-workspace",
                "--state",
                "open",
                "--limit",
                "20",
                "--json",
                "number,body,title",
            ])
        );
    }

    #[test]
    fn a_zero_exit_with_the_literal_answer_of_gh_is_the_body_and_the_title() {
        let (mut process, _calls) =
            Subject::answering(ChildExit::Code(0), "{\"body\":\"hola\",\"title\":\"Adios\"}\n", "");

        assert_eq!(
            process.body_of("alcaptar/demo-workspace", 516),
            Ok(IssueText::new("hola", "Adios"))
        );
    }

    #[test]
    fn a_zero_exit_with_the_literal_answer_of_gh_is_the_repo() {
        let (mut process, _calls) = Subject::answering(
            ChildExit::Code(0),
            "{\"nameWithOwner\":\"alcaptar/demo-workspace\"}\n",
            "",
        );

        assert_eq!(process.repo_of_directory(), Ok("alcaptar/demo-workspace".to_string()));
    }

    #[test]
    fn a_zero_exit_with_the_literal_answer_of_gh_is_the_list_of_issues() {
        let (mut process, _calls) = Subject::answering(
            ChildExit::Code(0),
            "[{\"body\":\"hola\",\"number\":9,\"title\":\"Adios\"}]\n",
            "",
        );

        assert_eq!(
            process.latest_open("alcaptar/demo-workspace", 20),
            Ok(vec![OpenIssue::new(9, "hola", "Adios")])
        );
    }

    #[test]
    fn a_non_zero_exit_is_a_failed_command_carrying_the_standard_error() {
        let (mut process, _calls) = Subject::answering(ChildExit::Code(4), "", "gh is not authenticated\n");

        assert_eq!(
            process.repo_of_directory(),
            Err(IssuesUnread::CommandFailed {
                reason: "gh is not authenticated".to_string()
            })
        );
    }

    #[test]
    fn a_non_zero_exit_without_standard_error_names_the_code() {
        let (mut process, _calls) = Subject::answering(ChildExit::Code(4), "", "");

        assert_eq!(
            process.repo_of_directory(),
            Err(IssuesUnread::CommandFailed {
                reason: "exited with code 4".to_string()
            })
        );
    }

    #[test]
    fn an_exit_by_a_signal_is_a_failed_command() {
        let (mut process, _calls) = Subject::answering(ChildExit::Signal, "", "");

        assert_eq!(
            process.repo_of_directory(),
            Err(IssuesUnread::CommandFailed {
                reason: "terminated by a signal".to_string()
            })
        );
    }

    #[test]
    fn a_program_that_cannot_be_launched_is_a_failed_command_carrying_why() {
        let (launcher, _calls) = ScriptedChildLauncher::unlaunchable("no such file");
        let mut process = Subject::over(launcher);

        assert_eq!(
            process.repo_of_directory(),
            Err(IssuesUnread::CommandFailed {
                reason: "no such file".to_string()
            })
        );
    }
}
