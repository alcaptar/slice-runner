mod the_threaded_workspace_binding {
    use std::time::Duration;

    use crate::application::queries::bind_workspace::BindWorkspace;
    use crate::domain::workspace_binding::WorkspaceBinding;
    use crate::domain::workspace_repo::WorkspaceRepo;
    use crate::infrastructure::threaded_workspace_binding::ThreadedWorkspaceBinding;
    use crate::tests::doubles::{GatedIssueSource, SteppedClock};
    use crate::tests::mothers::workspace_mother::WorkspaceMother;
    use crate::tests::waiting::Waiting;

    const PACE: Duration = Duration::from_millis(1);

    struct Gated;

    impl Gated {
        fn started() -> (ThreadedWorkspaceBinding, std::sync::mpsc::Sender<()>) {
            let (source, release) = GatedIssueSource::closed();
            let bind = BindWorkspace::new(
                source,
                SteppedClock::standing_still(),
                WorkspaceMother::cadence(),
                WorkspaceMother::id(),
            );

            (ThreadedWorkspaceBinding::start(bind, PACE), release)
        }
    }

    #[test]
    fn with_the_source_blocked_start_and_latest_return_at_once_and_the_state_is_unresolved() {
        let (mut binding, _release) = Gated::started();

        let state = binding.latest();

        assert_eq!(state.binding(), WorkspaceBinding::Unbound);
        assert_eq!(state.repo(), &WorkspaceRepo::Unknown);
        assert_eq!(state.id(), &WorkspaceMother::id());
    }

    #[test]
    fn once_the_source_is_released_latest_ends_up_delivering_the_bound_state() {
        let (mut binding, release) = Gated::started();

        release.send(()).unwrap();

        let state =
            Waiting::until(|| Some(binding.latest()).filter(|state| state.binding() != WorkspaceBinding::Unbound));
        assert_eq!(state.binding(), WorkspaceBinding::Bound(9));
        assert_eq!(binding.latest().binding(), WorkspaceBinding::Bound(9));
    }
}
