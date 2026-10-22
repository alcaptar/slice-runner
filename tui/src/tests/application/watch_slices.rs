mod grouping {
    use crate::domain::parent::Parent;
    use crate::tests::application::watching::Watching;
    use crate::tests::mothers::follow_line_mother::FollowLineMother;
    #[test]
    fn two_parents_of_the_same_repo_and_a_slice_without_parent_make_exactly_three_groups() {
        let watched = Watching::one_tick(Watching::lines(vec![
            FollowLineMother::orphan(170),
            FollowLineMother::child_of(141, 160),
            FollowLineMother::child_of(140, 150),
        ]));

        let groups: Vec<(String, Parent)> = watched
            .board()
            .groups()
            .iter()
            .map(|group| (group.repo().to_string(), group.parent()))
            .collect();

        assert_eq!(
            groups,
            vec![
                (FollowLineMother::REPO.to_string(), Parent::Issue(140)),
                (FollowLineMother::REPO.to_string(), Parent::Issue(141)),
                (FollowLineMother::REPO.to_string(), Parent::Absent),
            ]
        );
    }

    #[test]
    fn the_same_parent_number_in_two_repos_makes_two_groups() {
        let watched = Watching::one_tick(Watching::lines(vec![
            FollowLineMother::child_of_in_repo("alcaptar/one", 140, 150),
            FollowLineMother::child_of_in_repo("alcaptar/two", 140, 150),
        ]));

        assert_eq!(watched.board().groups().len(), 2);
    }
}

mod a_slice_that_reappears {
    use crate::application::queries::watch_slices::WatchSlices;
    use crate::domain::closure::Closure;
    use crate::domain::parent::Parent;
    use crate::domain::slice_board::SliceBoard;
    use crate::domain::step::Step;
    use crate::tests::application::watching::Watching;
    use crate::tests::doubles::{FixedProbe, ScriptedFollowSource};
    use crate::tests::mothers::follow_line_mother::FollowLineMother;
    #[test]
    fn keeps_a_single_row_with_the_state_of_the_second_line() {
        let first = FollowLineMother::child_of(140, 150);
        let second = FollowLineMother::merged(&first);

        let watched = Watching::one_tick(Watching::lines(vec![first, second]));

        let groups = watched.board().groups();
        assert_eq!(groups.len(), 1);
        assert_eq!(groups[0].rows().len(), 1);
        assert_eq!(groups[0].rows()[0].latest().step(), Some(Step::AwaitMerge));
        assert_eq!(groups[0].rows()[0].latest().closure(), Closure::Merged);
    }

    #[test]
    fn updates_across_ticks_without_duplicating_the_row() {
        let first = FollowLineMother::child_of(140, 150);
        let second = FollowLineMother::merged(&first);
        let mut watch = WatchSlices::new(
            ScriptedFollowSource::delivering(vec![Watching::lines(vec![first]), Watching::lines(vec![second])]),
            FixedProbe::everyone_alive(),
        );

        let after_first = watch.execute(SliceBoard::empty());
        let after_second = watch.execute(after_first.into_board());

        let groups = after_second.board().groups();
        assert_eq!(groups[0].rows().len(), 1);
        assert_eq!(groups[0].rows()[0].latest().closure(), Closure::Merged);
    }

    #[test]
    fn keeps_the_last_known_parent_and_name_when_the_later_line_arrives_without_them() {
        let first = FollowLineMother::child_of(140, 150);
        let second = FollowLineMother::merged_without_parent_or_name(&first);

        let watched = Watching::one_tick(Watching::lines(vec![first, second]));

        let groups = watched.board().groups();
        assert_eq!(groups.len(), 1);
        assert_eq!(groups[0].parent(), Parent::Issue(140));
        assert_eq!(groups[0].rows()[0].label(), FollowLineMother::NAME);
        assert_eq!(groups[0].rows()[0].latest().closure(), Closure::Merged);
    }
}

mod a_rejected_line {
    use crate::application::queries::watch_slices::WatchSlices;
    use crate::domain::slice_board::SliceBoard;
    use crate::tests::application::watching::Watching;
    use crate::tests::doubles::{FixedProbe, ScriptedFollowSource};
    use crate::tests::mothers::follow_line_mother::FollowLineMother;
    #[test]
    fn is_reported_without_losing_the_slices_already_listed() {
        let watched = Watching::one_tick(vec![
            Watching::lines(vec![FollowLineMother::child_of(140, 150)]).remove(0),
            Err(Watching::wrong_issue()),
        ]);

        assert_eq!(watched.rejection(), Some(&Watching::wrong_issue()));
        assert_eq!(watched.board().groups().len(), 1);
    }

    #[test]
    fn stays_reported_on_a_tick_with_nothing_new() {
        let mut watch = WatchSlices::new(
            ScriptedFollowSource::delivering(vec![vec![Err(Watching::wrong_issue())], vec![]]),
            FixedProbe::everyone_alive(),
        );

        let after_rejection = watch.execute(SliceBoard::empty());
        let quiet = watch.execute(after_rejection.into_board());

        assert_eq!(quiet.rejection(), Some(&Watching::wrong_issue()));
    }

    #[test]
    fn is_cleared_when_a_valid_line_arrives_afterwards() {
        let watched = Watching::one_tick(vec![
            Err(Watching::wrong_issue()),
            Watching::lines(vec![FollowLineMother::orphan(170)]).remove(0),
        ]);

        assert_eq!(watched.rejection(), None);
    }
}

mod the_board_shown_for_a_workspace {
    use crate::domain::slice_key::SliceKey;
    use crate::tests::application::watching::Watching;
    use crate::tests::mothers::follow_line_mother::FollowLineMother;
    use crate::tests::mothers::workspace_mother::WorkspaceMother;

    #[test]
    fn shows_nothing_while_the_workspace_has_no_parent_even_if_follow_emits_lines() {
        let watched = Watching::one_tick(Watching::lines(vec![
            FollowLineMother::child_of(140, 150),
            FollowLineMother::orphan(170),
        ]));

        let shown = watched.shown_for(&WorkspaceMother::unbound());

        assert!(shown.board().groups().is_empty());
    }

    #[test]
    fn bound_to_a_parent_shows_only_its_slices_in_the_repo_of_the_workspace() {
        let watched = Watching::one_tick(Watching::lines(vec![
            FollowLineMother::child_of(140, 150),
            FollowLineMother::child_of(141, 160),
            FollowLineMother::child_of_in_repo("alcaptar/other", 140, 170),
            FollowLineMother::orphan(180),
        ]));

        let shown = watched.shown_for(&WorkspaceMother::bound_to(140));

        let keys: Vec<SliceKey> = shown
            .board()
            .groups()
            .iter()
            .flat_map(|group| group.rows().iter().map(|row| row.key().clone()))
            .collect();
        assert_eq!(keys, vec![Watching::key(150)]);
        assert_eq!(shown.board().groups()[0].repo(), FollowLineMother::REPO);
    }

    #[test]
    fn carries_the_title_of_the_workspace_it_is_shown_for() {
        let watched = Watching::one_tick(Watching::lines(vec![FollowLineMother::child_of(140, 150)]));

        assert_eq!(watched.title(), None);
        assert_eq!(
            watched.shown_for(&WorkspaceMother::bound_to(140)).title(),
            Some(WorkspaceMother::PARENT_TITLE)
        );
        assert_eq!(watched.shown_for(&WorkspaceMother::unbound()).title(), None);
    }

    #[test]
    fn keeps_the_rejection_and_leaves_the_accumulated_board_whole_for_the_next_tick() {
        let watched = Watching::one_tick(vec![
            Watching::lines(vec![FollowLineMother::child_of(140, 150)]).remove(0),
            Watching::lines(vec![FollowLineMother::orphan(180)]).remove(0),
            Err(Watching::wrong_issue()),
        ]);

        let shown = watched.shown_for(&WorkspaceMother::unbound());

        assert_eq!(shown.rejection(), Some(&Watching::wrong_issue()));
        let accumulated = watched.into_board();
        assert_eq!(accumulated.groups().len(), 2);
    }

    #[test]
    fn lines_that_arrived_before_the_binding_show_up_as_soon_as_it_happens() {
        let watched = Watching::one_tick(Watching::lines(vec![FollowLineMother::child_of(140, 150)]));
        assert!(
            watched
                .shown_for(&WorkspaceMother::unbound())
                .board()
                .groups()
                .is_empty()
        );

        let shown = watched.shown_for(&WorkspaceMother::bound_to(140));

        assert_eq!(shown.board().groups().len(), 1);
    }
}

mod the_process_of_a_slice {
    use crate::application::queries::watch_slices::WatchSlices;
    use crate::domain::attention::Attention;
    use crate::domain::follow_entry::FollowEntry;
    use crate::domain::slice_board::SliceBoard;
    use crate::tests::application::watching::Watching;
    use crate::tests::doubles::{FixedProbe, ScriptedFollowSource, UnaskedProbe};
    use crate::tests::mothers::screen_mother::ScreenMother;

    #[test]
    fn a_running_slice_whose_process_is_gone_needs_you_and_one_whose_process_lives_runs() {
        let watched = Watching::entries(
            ScreenMother::feature(),
            FixedProbe::alive_only(&[ScreenMother::JUDGED_PID]),
        );

        let board = watched.board();
        assert_eq!(
            board.row(&ScreenMother::key(3)).unwrap().attention(),
            Attention::NeedsYou
        );
        assert_eq!(
            board.row(&ScreenMother::key(2)).unwrap().attention(),
            Attention::Running
        );
    }

    #[test]
    fn is_not_asked_about_a_slice_that_is_pending_blocked_or_merged() {
        let only_settled: Vec<_> = ScreenMother::feature()
            .into_iter()
            .filter(|entry| match entry {
                FollowEntry::Transition(line) => [529, 530, 531].contains(&line.issue()),
                FollowEntry::Activity(_) => false,
            })
            .collect();
        let mut watch = WatchSlices::new(
            ScriptedFollowSource::delivering(vec![only_settled.into_iter().map(Ok).collect()]),
            UnaskedProbe,
        );

        let watched = watch.execute(SliceBoard::empty());

        assert_eq!(watched.board().groups()[0].rows().len(), 3);
    }
}

mod a_transition_that_repeats_the_last_one {
    use crate::domain::step::Step;
    use crate::tests::application::watching::Watching;
    use crate::tests::mothers::follow_line_mother::FollowLineMother;

    #[test]
    fn leaves_a_single_entry_in_the_history_of_its_slice() {
        let first = FollowLineMother::child_of(140, 150);

        let watched = Watching::one_tick(Watching::lines(vec![
            first.clone(),
            FollowLineMother::moved_to(&first, Step::AwaitCi),
            FollowLineMother::moved_to(&first, Step::AwaitCi),
            FollowLineMother::moved_to(&first, Step::AwaitCi),
        ]));

        assert_eq!(watched.board().row(&Watching::key(150)).unwrap().transitions().len(), 2);
    }
}

mod a_reopened_slice {
    use crate::domain::attention::Attention;
    use crate::tests::application::watching::Watching;
    use crate::tests::doubles::FixedProbe;
    use crate::tests::mothers::screen_mother::ScreenMother;

    #[test]
    fn does_not_inherit_the_process_of_the_run_that_closed() {
        let watched = Watching::entries(ScreenMother::reopened_without_a_process(), FixedProbe::alive_only(&[]));

        let row = watched.board().row(&ScreenMother::key(4)).unwrap();

        assert_eq!(row.pid(), None);
        assert_eq!(row.attention(), Attention::Running);
    }
}

mod a_repeated_line_with_a_new_spend {
    use crate::tests::application::watching::Watching;
    use crate::tests::mothers::screen_mother::ScreenMother;

    #[test]
    fn keeps_one_entry_with_the_new_spend_and_the_first_moment() {
        let (first, again) = ScreenMother::the_same_step_twice_with_more_spend();
        let first_at = first.clone().into_parts().1.at();

        let watched = Watching::one_tick(Watching::lines(vec![first, again]));

        let row = watched.board().row(&ScreenMother::key(3)).unwrap();
        assert_eq!(row.transitions().len(), 1);
        assert_eq!(row.latest().at(), first_at);
        assert!((row.latest().spend().cost_usd() - 45.0).abs() < f64::EPSILON);
    }
}
