mod reopening_a_workspace {
    use std::path::PathBuf;

    use crate::application::actions::reopen_workspace::{ReopenWorkspace, ReopenWorkspaceParams};
    use crate::domain::errors::{IssuesUnread, WorkspaceNotReopened};
    use crate::domain::workspace_binding::WorkspaceBinding;
    use crate::domain::workspace_repo::WorkspaceRepo;
    use crate::tests::doubles::{Call, Calls, ScriptedIssueSource, ScriptedTranscripts};
    use crate::tests::mothers::workspace_mother::WorkspaceMother;

    const PARENT: u64 = 516;

    struct Scenario;

    impl Scenario {
        fn source(body: Result<String, IssuesUnread>) -> (ScriptedIssueSource, Calls) {
            let (source, calls) = ScriptedIssueSource::answering(vec![Ok(WorkspaceMother::REPO.to_string())], vec![]);

            (source.with_bodies(vec![body]), calls)
        }

        fn params() -> ReopenWorkspaceParams {
            ReopenWorkspaceParams::new(PathBuf::from("/work/repo"), PARENT)
        }

        fn marked() -> String {
            WorkspaceMother::body_marked_with(WorkspaceMother::UUID)
        }
    }

    #[test]
    fn resumes_the_session_of_the_mark_when_its_transcript_is_on_disk() {
        let (source, _) = Scenario::source(Ok(Scenario::marked()));

        let reopened = ReopenWorkspace::new(source, ScriptedTranscripts::present())
            .execute(Scenario::params())
            .unwrap();

        assert_eq!(
            reopened.launch().argv(),
            ["claude", "--resume", WorkspaceMother::UUID].map(str::to_string)
        );
        assert_eq!(reopened.launch().directory(), PathBuf::from("/work/repo"));
        assert_eq!(
            reopened.launch().environment(),
            [("SLICE_RUNNER_WORKSPACE".to_string(), WorkspaceMother::UUID.to_string())]
        );
    }

    #[test]
    fn opens_a_new_session_with_the_same_id_and_without_the_slash_command_when_the_transcript_expired() {
        let (source, _) = Scenario::source(Ok(Scenario::marked()));

        let reopened = ReopenWorkspace::new(source, ScriptedTranscripts::absent())
            .execute(Scenario::params())
            .unwrap();

        assert_eq!(
            reopened.launch().argv(),
            ["claude", "--session-id", WorkspaceMother::UUID].map(str::to_string)
        );
        assert_eq!(
            reopened.launch().environment(),
            [("SLICE_RUNNER_WORKSPACE".to_string(), WorkspaceMother::UUID.to_string())]
        );
    }

    #[test]
    fn reads_the_body_of_the_parent_in_the_repo_of_the_directory_and_nothing_else() {
        let (source, calls) = Scenario::source(Ok(Scenario::marked()));

        ReopenWorkspace::new(source, ScriptedTranscripts::present())
            .execute(Scenario::params())
            .unwrap();

        assert_eq!(
            *calls.lock().unwrap(),
            [
                Call::RepoView,
                Call::IssueView {
                    repo: WorkspaceMother::REPO.to_string(),
                    number: PARENT
                }
            ]
        );
    }

    #[test]
    fn the_state_is_born_bound_to_the_parent_with_its_repo_known() {
        let (source, _) = Scenario::source(Ok(Scenario::marked()));

        let state = ReopenWorkspace::new(source, ScriptedTranscripts::present())
            .execute(Scenario::params())
            .unwrap()
            .into_state();

        assert_eq!(state.binding(), WorkspaceBinding::Bound(PARENT));
        assert_eq!(state.id().as_str(), WorkspaceMother::UUID);
        assert_eq!(state.repo(), &WorkspaceRepo::Known(WorkspaceMother::REPO.to_string()));
    }

    #[test]
    fn the_state_carries_the_title_of_the_parent() {
        let (source, _) = Scenario::source(Ok(Scenario::marked()));

        let state = ReopenWorkspace::new(source, ScriptedTranscripts::present())
            .execute(Scenario::params())
            .unwrap()
            .into_state();

        assert_eq!(state.title(), Some(WorkspaceMother::PARENT_TITLE));
    }

    #[test]
    fn a_parent_without_mark_was_not_designed_in_a_workspace() {
        let (source, _) = Scenario::source(Ok(WorkspaceMother::body_without_marker()));

        let outcome = ReopenWorkspace::new(source, ScriptedTranscripts::present()).execute(Scenario::params());

        let error = outcome.err().unwrap();
        assert_eq!(error, WorkspaceNotReopened::Unmarked { parent: PARENT });
        assert_eq!(error.to_string(), "parent #516 was not designed in a workspace");
    }

    #[test]
    fn a_gh_that_fails_is_propagated_as_unread() {
        let unread = IssuesUnread::CommandFailed {
            reason: "boom".to_string(),
        };
        let (source, _) = Scenario::source(Err(unread.clone()));

        let outcome = ReopenWorkspace::new(source, ScriptedTranscripts::present()).execute(Scenario::params());

        assert_eq!(outcome.err(), Some(WorkspaceNotReopened::Unread(unread)));
    }
}
