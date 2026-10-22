use std::time::Duration;

use crate::application::queries::bind_workspace::BindWorkspace;
use crate::domain::errors::IssuesUnread;
use crate::domain::open_issue::OpenIssue;
use crate::tests::doubles::{Call, Calls, ScriptedIssueSource, SteppedClock};
use crate::tests::mothers::workspace_mother::WorkspaceMother;

pub struct Binding;

impl Binding {
    pub fn asking(
        repos: Vec<Result<String, IssuesUnread>>,
        lists: Vec<Result<Vec<OpenIssue>, IssuesUnread>>,
    ) -> (BindWorkspace<ScriptedIssueSource, SteppedClock>, SteppedClock, Calls) {
        let (source, calls) = ScriptedIssueSource::answering(repos, lists);
        let clock = SteppedClock::standing_still();
        let bind = BindWorkspace::new(source, clock.clone(), WorkspaceMother::cadence(), WorkspaceMother::id());

        (bind, clock, calls)
    }

    pub fn repo() -> Vec<Result<String, IssuesUnread>> {
        vec![Ok(WorkspaceMother::REPO.to_string())]
    }

    pub fn timed_out() -> IssuesUnread {
        IssuesUnread::TimedOut {
            budget: Duration::from_secs(10),
        }
    }

    pub fn issue_lists(calls: &Calls) -> usize {
        calls
            .lock()
            .unwrap()
            .iter()
            .filter(|call| matches!(call, Call::IssueList { .. }))
            .count()
    }

    pub fn next_interval(clock: &SteppedClock) {
        clock.advance(WorkspaceMother::INTERVAL);
    }
}

mod a_workspace_without_a_parent {
    use crate::domain::workspace_binding::WorkspaceBinding;
    use crate::domain::workspace_repo::WorkspaceRepo;
    use crate::tests::application::bind_workspace::Binding;
    use crate::tests::doubles::Call;
    use crate::tests::mothers::workspace_mother::WorkspaceMother;

    #[test]
    fn stays_unbound_and_knows_its_repo_and_its_id() {
        let (mut bind, _, _) = Binding::asking(Binding::repo(), vec![Ok(vec![WorkspaceMother::unrelated_issue(7)])]);

        let state = bind.execute();

        assert_eq!(state.binding(), WorkspaceBinding::Unbound);
        assert_eq!(state.repo(), &WorkspaceRepo::Known(WorkspaceMother::REPO.to_string()));
        assert_eq!(state.id(), &WorkspaceMother::id());
        assert_eq!(state.warning(), None);
    }

    #[test]
    fn has_no_title_while_it_is_unbound() {
        let (mut bind, _, _) = Binding::asking(Binding::repo(), vec![Ok(vec![WorkspaceMother::unrelated_issue(7)])]);

        assert_eq!(bind.execute().title(), None);
    }

    #[test]
    fn asks_for_the_last_twenty_open_issues_of_the_repo_of_the_directory() {
        let (mut bind, _, calls) = Binding::asking(Binding::repo(), vec![Ok(vec![])]);

        bind.execute();

        assert_eq!(
            *calls.lock().unwrap(),
            vec![
                Call::RepoView,
                Call::IssueList {
                    repo: WorkspaceMother::REPO.to_string(),
                    limit: 20
                }
            ]
        );
    }
}

mod the_marker_of_the_workspace {
    use crate::application::queries::bind_workspace::BindWorkspace;
    use crate::domain::open_issue::OpenIssue;
    use crate::domain::workspace_binding::WorkspaceBinding;
    use crate::tests::application::bind_workspace::Binding;
    use crate::tests::doubles::{ScriptedIssueSource, SteppedClock};
    use crate::tests::infrastructure::contract::MarkerContract;
    use crate::tests::mothers::workspace_mother::WorkspaceMother;

    #[test]
    fn binds_to_the_first_issue_that_ends_with_it() {
        let (mut bind, _, _) = Binding::asking(
            Binding::repo(),
            vec![Ok(vec![
                WorkspaceMother::unrelated_issue(7),
                WorkspaceMother::parent_of_this_workspace(9),
                WorkspaceMother::parent_of_this_workspace(11),
            ])],
        );

        assert_eq!(bind.execute().binding(), WorkspaceBinding::Bound(9));
    }

    #[test]
    fn takes_the_title_of_the_issue_it_binds_to() {
        let (mut bind, _, _) = Binding::asking(
            Binding::repo(),
            vec![Ok(vec![
                WorkspaceMother::unrelated_issue(7),
                WorkspaceMother::parent_of_this_workspace(9),
            ])],
        );

        assert_eq!(bind.execute().title(), Some(WorkspaceMother::PARENT_TITLE));
    }

    #[test]
    fn of_another_workspace_does_not_bind() {
        let (mut bind, _, _) = Binding::asking(
            Binding::repo(),
            vec![Ok(vec![WorkspaceMother::parent_marked_with(
                9,
                WorkspaceMother::OTHER_UUID,
            )])],
        );

        assert_eq!(bind.execute().binding(), WorkspaceBinding::Unbound);
    }

    #[test]
    fn written_in_the_middle_of_the_body_does_not_bind() {
        let body = format!(
            "{}\n\nand then more text\n",
            WorkspaceMother::marker_of(WorkspaceMother::UUID)
        );
        let (mut bind, _, _) = Binding::asking(Binding::repo(), vec![Ok(vec![OpenIssue::new(9, &body, "titulo")])]);

        assert_eq!(bind.execute().binding(), WorkspaceBinding::Unbound);
    }

    #[test]
    fn every_example_of_the_contract_on_disk_binds_its_workspace() {
        let contract = MarkerContract::on_disk();

        assert!(!contract.examples.is_empty());
        for example in &contract.examples {
            let id = contract.workspace_of(example);
            let issue = OpenIssue::new(9, &format!("## Intencion\n\nalgo\n\n{example}\n"), "titulo");
            let (source, _) = ScriptedIssueSource::answering(Binding::repo(), vec![Ok(vec![issue])]);
            let mut bind = BindWorkspace::new(source, SteppedClock::standing_still(), WorkspaceMother::cadence(), id);

            assert_eq!(bind.execute().binding(), WorkspaceBinding::Bound(9), "{example}");
        }
    }
}

mod the_queries {
    use std::time::Duration;

    use crate::domain::workspace_binding::WorkspaceBinding;
    use crate::tests::application::bind_workspace::Binding;
    use crate::tests::mothers::workspace_mother::WorkspaceMother;

    #[test]
    fn are_exactly_two_when_the_marker_shows_up_in_the_second_even_if_the_clock_keeps_advancing() {
        let (mut bind, clock, calls) = Binding::asking(
            Binding::repo(),
            vec![
                Ok(vec![WorkspaceMother::unrelated_issue(7)]),
                Ok(vec![WorkspaceMother::parent_of_this_workspace(9)]),
            ],
        );

        bind.execute();
        Binding::next_interval(&clock);
        bind.execute();
        for _ in 0..5 {
            Binding::next_interval(&clock);
            assert_eq!(bind.execute().binding(), WorkspaceBinding::Bound(9));
        }

        assert_eq!(Binding::issue_lists(&calls), 2);
    }

    #[test]
    fn do_not_repeat_before_the_interval_has_passed() {
        let (mut bind, clock, calls) = Binding::asking(Binding::repo(), vec![Ok(vec![]), Ok(vec![])]);

        bind.execute();
        clock.advance(WorkspaceMother::INTERVAL.saturating_sub(Duration::from_millis(1)));
        bind.execute();

        assert_eq!(Binding::issue_lists(&calls), 1);
    }

    #[test]
    fn repeat_once_the_interval_has_passed() {
        let (mut bind, clock, calls) = Binding::asking(Binding::repo(), vec![Ok(vec![]), Ok(vec![])]);

        bind.execute();
        Binding::next_interval(&clock);
        bind.execute();

        assert_eq!(Binding::issue_lists(&calls), 2);
    }
}

mod a_failed_read {
    use crate::domain::errors::IssuesUnread;
    use crate::domain::workspace_binding::WorkspaceBinding;
    use crate::domain::workspace_repo::WorkspaceRepo;
    use crate::tests::application::bind_workspace::Binding;
    use crate::tests::doubles::Call;
    use crate::tests::mothers::workspace_mother::WorkspaceMother;

    #[test]
    fn of_the_issues_is_a_warning_and_the_next_interval_asks_again_and_clears_it() {
        let failed = IssuesUnread::CommandFailed {
            reason: "gh is not authenticated".to_string(),
        };
        let (mut bind, clock, _) = Binding::asking(
            Binding::repo(),
            vec![
                Err(failed.clone()),
                Ok(vec![WorkspaceMother::parent_of_this_workspace(9)]),
            ],
        );

        let first = bind.execute();
        Binding::next_interval(&clock);
        let second = bind.execute();

        assert_eq!(first.warning(), Some(&failed));
        assert_eq!(first.binding(), WorkspaceBinding::Unbound);
        assert_eq!(second.warning(), None);
        assert_eq!(second.binding(), WorkspaceBinding::Bound(9));
    }

    #[test]
    fn because_the_budget_ran_out_is_a_warning_and_asks_again_at_the_next_interval() {
        let (mut bind, clock, calls) = Binding::asking(
            Binding::repo(),
            vec![Err(Binding::timed_out()), Err(Binding::timed_out())],
        );

        let first = bind.execute();
        Binding::next_interval(&clock);
        bind.execute();

        assert_eq!(first.warning(), Some(&Binding::timed_out()));
        assert_eq!(Binding::issue_lists(&calls), 2);
    }

    #[test]
    fn of_the_repo_is_a_warning_leaves_it_unknown_and_resolves_it_at_the_next_interval() {
        let (mut bind, clock, calls) = Binding::asking(
            vec![Err(Binding::timed_out()), Ok(WorkspaceMother::REPO.to_string())],
            vec![Ok(vec![WorkspaceMother::parent_of_this_workspace(9)])],
        );

        let first = bind.execute();
        Binding::next_interval(&clock);
        let second = bind.execute();

        assert_eq!(first.warning(), Some(&Binding::timed_out()));
        assert_eq!(first.repo(), &WorkspaceRepo::Unknown);
        assert_eq!(Binding::issue_lists(&calls), 1);
        assert_eq!(second.repo(), &WorkspaceRepo::Known(WorkspaceMother::REPO.to_string()));
        assert_eq!(second.binding(), WorkspaceBinding::Bound(9));
    }

    #[test]
    fn the_repo_is_resolved_once_and_not_asked_again_once_known() {
        let (mut bind, clock, calls) = Binding::asking(Binding::repo(), vec![Ok(vec![]), Ok(vec![])]);

        bind.execute();
        Binding::next_interval(&clock);
        bind.execute();

        let repo_views = calls
            .lock()
            .unwrap()
            .iter()
            .filter(|call| **call == Call::RepoView)
            .count();
        assert_eq!(repo_views, 1);
    }
}

mod the_state_before_any_read {
    use crate::application::queries::bind_workspace::WorkspaceState;
    use crate::domain::workspace_binding::WorkspaceBinding;
    use crate::domain::workspace_repo::WorkspaceRepo;
    use crate::tests::mothers::workspace_mother::WorkspaceMother;

    #[test]
    fn has_no_repo_no_feature_and_no_warning() {
        let state = WorkspaceState::unresolved(WorkspaceMother::id());

        assert_eq!(state.repo(), &WorkspaceRepo::Unknown);
        assert_eq!(state.binding(), WorkspaceBinding::Unbound);
        assert_eq!(state.warning(), None);
        assert_eq!(state.id(), &WorkspaceMother::id());
    }
}

mod a_workspace_born_bound {
    use crate::application::queries::bind_workspace::{BindWorkspace, WorkspaceState};
    use crate::domain::workspace_binding::WorkspaceBinding;
    use crate::tests::doubles::{ScriptedIssueSource, SteppedClock};
    use crate::tests::mothers::workspace_mother::WorkspaceMother;

    #[test]
    fn stays_bound_to_its_parent_without_asking_gh_anything() {
        let (source, calls) = ScriptedIssueSource::answering(vec![], vec![]);
        let state = WorkspaceState::bound(
            WorkspaceMother::REPO.to_string(),
            WorkspaceMother::id(),
            516,
            WorkspaceMother::PARENT_TITLE,
        );
        let mut bind = BindWorkspace::from_state(
            source,
            SteppedClock::standing_still(),
            WorkspaceMother::cadence(),
            state,
        );

        let current = bind.execute();

        assert_eq!(current.binding(), WorkspaceBinding::Bound(516));
        assert!(calls.lock().unwrap().is_empty());
    }
}
