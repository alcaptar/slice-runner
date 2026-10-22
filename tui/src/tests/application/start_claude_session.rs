mod starting_the_claude_session {
    use std::path::PathBuf;

    use crate::application::actions::start_claude_session::{StartClaudeSession, StartClaudeSessionParams};
    use crate::tests::doubles::FixedWorkspaceIds;

    const UUID: &str = "0b9a6f0e-6f3c-4a54-9d0e-3b1f6f0c2a11";

    #[test]
    fn launches_claude_with_the_generated_id_in_the_current_directory_and_the_workspace_variable() {
        let mut start = StartClaudeSession::new(FixedWorkspaceIds::always(UUID));

        let launch = start.execute(StartClaudeSessionParams::in_directory(PathBuf::from("/work/repo")));

        assert_eq!(
            launch.argv(),
            ["claude", "--session-id", UUID, "/slice-spec"].map(str::to_string)
        );
        assert_eq!(launch.directory(), PathBuf::from("/work/repo"));
        assert_eq!(
            launch.environment(),
            [("SLICE_RUNNER_WORKSPACE".to_string(), UUID.to_string())]
        );
    }

    #[test]
    fn hands_the_generated_workspace_id_to_the_caller_without_going_through_the_environment() {
        let mut start = StartClaudeSession::new(FixedWorkspaceIds::always(UUID));

        let launch = start.execute(StartClaudeSessionParams::in_directory(PathBuf::from("/work/repo")));

        assert_eq!(launch.workspace().as_str(), UUID);
    }
}
