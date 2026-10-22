use std::path::PathBuf;

use crate::domain::pane_size::PaneSize;
use crate::domain::session_launch::SessionLaunch;
use crate::domain::workspace_id::WorkspaceId;
use crate::infrastructure::endless_pty_session::EndlessPtySession;

pub struct Launches;

impl Launches {
    pub const WORKSPACE: &'static str = "0b9a6f0e-6f3c-4a54-9d0e-3b1f6f0c2a11";

    pub fn of(argv: Vec<String>) -> SessionLaunch {
        SessionLaunch::new(Self::workspace(), argv, PathBuf::from("/work"), Vec::new())
    }

    pub fn claude() -> SessionLaunch {
        Self::of(vec!["claude".to_string()])
    }

    pub fn for_the_workspace(argv: Vec<String>, directory: PathBuf) -> SessionLaunch {
        SessionLaunch::for_workspace(Self::workspace(), argv, directory)
    }

    fn workspace() -> WorkspaceId {
        WorkspaceId::parse(Self::WORKSPACE).unwrap()
    }

    pub fn size() -> PaneSize {
        PaneSize::new(24, 80)
    }

    pub fn text_of(session: &EndlessPtySession) -> String {
        session.with_screen(vt100::Screen::contents)
    }
}

mod the_endless_pty_session {
    use std::panic::{AssertUnwindSafe, catch_unwind};
    use std::path::PathBuf;

    use crate::domain::errors::SessionNotLaunched;
    use crate::domain::pane_size::PaneSize;
    use crate::infrastructure::endless_pty_session::EndlessPtySession;
    use crate::tests::doubles::{ChildCall, PtyCall, ScriptedPtyLauncher, SteppedClock};
    use crate::tests::infrastructure::endless_pty_session::Launches;
    use crate::tests::waiting::Waiting;

    #[test]
    fn the_bytes_the_reader_delivers_reach_the_screen() {
        let (launcher, _probe) = ScriptedPtyLauncher::printing("hello from claude");
        let session = EndlessPtySession::spawn(
            &launcher,
            &Launches::claude(),
            Launches::size(),
            SteppedClock::standing_still(),
        )
        .unwrap();

        let text = Waiting::until(|| Some(Launches::text_of(&session)).filter(|text| text.contains("hello")));

        assert_eq!(text, "hello from claude");
    }

    #[test]
    fn what_is_written_in_the_session_reaches_the_writer() {
        let (launcher, probe) = ScriptedPtyLauncher::printing("");
        let mut session = EndlessPtySession::spawn(
            &launcher,
            &Launches::claude(),
            Launches::size(),
            SteppedClock::standing_still(),
        )
        .unwrap();

        session.write(b"ls\r");
        session.write(b"\x03");

        assert_eq!(probe.written(), b"ls\r\x03");
    }

    #[test]
    fn a_resize_reaches_the_pty_with_the_size_asked_and_resizes_the_screen() {
        let (launcher, probe) = ScriptedPtyLauncher::printing("");
        let mut session = EndlessPtySession::spawn(
            &launcher,
            &Launches::claude(),
            Launches::size(),
            SteppedClock::standing_still(),
        )
        .unwrap();

        session.resize(PaneSize::new(10, 30));

        assert_eq!(probe.calls()[1..], [PtyCall::Resized(PaneSize::new(10, 30))]);
        assert_eq!(session.with_screen(vt100::Screen::size), (10, 30));
    }

    #[test]
    fn the_launcher_gets_the_command_the_directory_and_the_workspace_variable() {
        let (launcher, probe) = ScriptedPtyLauncher::printing("");
        let launch = Launches::for_the_workspace(
            vec!["claude".to_string(), "--resume".to_string()],
            PathBuf::from("/work/repo"),
        );

        let _session = EndlessPtySession::spawn(
            &launcher,
            &launch,
            PaneSize::new(24, 40),
            SteppedClock::standing_still(),
        )
        .unwrap();

        assert_eq!(
            probe.calls(),
            [PtyCall::Launched {
                argv: vec!["claude".to_string(), "--resume".to_string()],
                directory: PathBuf::from("/work/repo"),
                environment: vec![("SLICE_RUNNER_WORKSPACE".to_string(), Launches::WORKSPACE.to_string())],
                size: PaneSize::new(24, 40),
            }]
        );
    }

    #[test]
    fn it_reports_the_end_of_the_child_only_once_it_ends() {
        let (launcher, probe) = ScriptedPtyLauncher::printing("");
        let mut session = EndlessPtySession::spawn(
            &launcher,
            &Launches::claude(),
            Launches::size(),
            SteppedClock::standing_still(),
        )
        .unwrap();
        assert!(!session.has_ended());

        probe.end_the_child();

        assert!(session.has_ended());
    }

    #[test]
    fn dropping_the_session_kills_and_waits_the_child() {
        let (launcher, probe) = ScriptedPtyLauncher::printing("");
        let session = EndlessPtySession::spawn(
            &launcher,
            &Launches::claude(),
            Launches::size(),
            SteppedClock::standing_still(),
        )
        .unwrap();

        drop(session);

        assert_eq!(probe.child_calls(), [ChildCall::Killed, ChildCall::Waited]);
    }

    #[test]
    fn the_child_is_killed_and_waited_when_the_interface_falls_by_a_panic() {
        let (launcher, probe) = ScriptedPtyLauncher::printing("");

        let outcome = catch_unwind(AssertUnwindSafe(|| {
            let _session = EndlessPtySession::spawn(
                &launcher,
                &Launches::claude(),
                Launches::size(),
                SteppedClock::standing_still(),
            )
            .unwrap();
            panic!("the interface fell");
        }));

        assert!(outcome.is_err());
        assert_eq!(probe.child_calls(), [ChildCall::Killed, ChildCall::Waited]);
    }

    #[test]
    fn a_launcher_that_fails_is_a_typed_rejection_carrying_why() {
        let (launcher, _probe) = ScriptedPtyLauncher::unlaunchable("no such file");

        let rejected = EndlessPtySession::spawn(
            &launcher,
            &Launches::claude(),
            Launches::size(),
            SteppedClock::standing_still(),
        )
        .err();

        assert_eq!(
            rejected,
            Some(SessionNotLaunched {
                reason: "no such file".to_string()
            })
        );
    }

    #[test]
    fn an_empty_command_is_rejected_without_asking_the_launcher() {
        let (launcher, probe) = ScriptedPtyLauncher::printing("");

        let rejected = EndlessPtySession::spawn(
            &launcher,
            &Launches::of(Vec::new()),
            Launches::size(),
            SteppedClock::standing_still(),
        )
        .err();

        assert_eq!(
            rejected,
            Some(SessionNotLaunched {
                reason: "empty command".to_string()
            })
        );
        assert!(probe.calls().is_empty());
    }

    #[test]
    fn while_a_frame_is_open_the_painted_screen_lags_behind_the_live_one_the_keys_read() {
        let (launcher, _probe) = ScriptedPtyLauncher::printing("before\x1b[?2026h\x1b[?2004h after");
        let session = EndlessPtySession::spawn(
            &launcher,
            &Launches::claude(),
            Launches::size(),
            SteppedClock::standing_still(),
        )
        .unwrap();

        Waiting::until(|| session.with_screen(vt100::Screen::bracketed_paste).then_some(()));

        assert_eq!(Launches::text_of(&session), "before after");
        assert_eq!(session.with_painted_screen(vt100::Screen::contents), "before");
    }
}
