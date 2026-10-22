mod the_endless_follow_process {
    use std::panic::{AssertUnwindSafe, catch_unwind};

    use crate::domain::errors::FollowLineRejected;
    use crate::domain::follow_entry::FollowEntry;
    use crate::domain::follow_source::FollowSource;
    use crate::infrastructure::child_launcher::{Input, Launch, Stream};
    use crate::infrastructure::endless_follow_process::EndlessFollowProcess;
    use crate::tests::doubles::{ChildCall, ScriptedChildLauncher};
    use crate::tests::waiting::Waiting;

    const ACTIVITY_LINE: &str = r#"{"version":2,"kind":"activity","ts":1,"repo":"a/b","issue":1,"slice_id":"slice-01","actor":"judge","tool":"Read","target":"x"}"#;
    const ARGV: [&str; 3] = ["slice-runner", "follow", "--json"];

    #[test]
    fn launches_the_command_reading_only_the_standard_output() {
        let (launcher, calls) = ScriptedChildLauncher::streaming("");

        let _process = EndlessFollowProcess::spawn(&launcher, &ARGV).unwrap();

        assert_eq!(
            calls.lock().unwrap()[0],
            ChildCall::Launched {
                argv: ARGV.map(ToString::to_string).to_vec(),
                launch: Launch::new(Input::Empty, Stream::Read, Stream::Discard),
            }
        );
    }

    #[test]
    fn delivers_each_line_parsed_and_reports_when_follow_ends() {
        let (launcher, _calls) = ScriptedChildLauncher::streaming(&format!("{ACTIVITY_LINE}\ngarbage\n"));
        let mut process = EndlessFollowProcess::spawn(&launcher, &ARGV).unwrap();
        let mut delivered = Vec::new();

        Waiting::until(|| {
            delivered.extend(process.pending());
            (delivered.len() >= 3).then_some(())
        });

        assert!(
            matches!(delivered[0], Ok(FollowEntry::Activity(_))),
            "{:?}",
            delivered[0]
        );
        assert_eq!(
            delivered[1],
            Err(FollowLineRejected::NotJson {
                line: "garbage".to_string()
            })
        );
        assert_eq!(delivered[2], Err(FollowLineRejected::FollowEnded));
    }

    #[test]
    fn dropping_the_adapter_kills_and_waits_the_child() {
        let (launcher, calls) = ScriptedChildLauncher::streaming("");
        let process = EndlessFollowProcess::spawn(&launcher, &ARGV).unwrap();

        drop(process);

        assert_eq!(
            calls.lock().unwrap().iter().skip(1).cloned().collect::<Vec<_>>(),
            [ChildCall::Killed, ChildCall::Waited]
        );
    }

    #[test]
    fn the_child_is_killed_and_waited_when_the_interface_falls_by_a_panic() {
        let (launcher, calls) = ScriptedChildLauncher::streaming("");

        let outcome = catch_unwind(AssertUnwindSafe(|| {
            let _process = EndlessFollowProcess::spawn(&launcher, &ARGV).unwrap();
            panic!("the interface fell");
        }));

        assert!(outcome.is_err());
        assert_eq!(
            calls.lock().unwrap().iter().skip(1).cloned().collect::<Vec<_>>(),
            [ChildCall::Killed, ChildCall::Waited]
        );
    }

    #[test]
    fn a_launcher_that_fails_is_a_typed_rejection_carrying_why() {
        let (launcher, _calls) = ScriptedChildLauncher::unlaunchable("no such file");

        let rejected = EndlessFollowProcess::spawn(&launcher, &ARGV).err();

        assert_eq!(
            rejected,
            Some(FollowLineRejected::FollowNotLaunched {
                reason: "no such file".to_string()
            })
        );
    }
}
