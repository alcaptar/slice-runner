mod the_comparison_of_a_slice {
    use crate::domain::step::Step;
    use crate::tests::application::watching::Watching;
    use crate::tests::mothers::follow_line_mother::FollowLineMother;

    #[test]
    fn survives_a_later_transition_that_does_not_carry_it() {
        let first = FollowLineMother::child_of(140, 150);
        let watched = Watching::one_tick(Watching::lines(vec![
            first.clone(),
            FollowLineMother::awaiting_merge_with_comparison(&first),
            FollowLineMother::moved_to(&first, Step::AwaitCi),
        ]));

        let row = watched.board().row(&Watching::key(150)).unwrap();

        assert_eq!(row.comparison(), Some(FollowLineMother::COMPARISON));
    }

    #[test]
    fn is_absent_when_no_transition_of_the_slice_ever_carried_it() {
        let first = FollowLineMother::child_of(140, 150);
        let watched = Watching::one_tick(Watching::lines(vec![
            first.clone(),
            FollowLineMother::moved_to(&first, Step::Implement),
        ]));

        let row = watched.board().row(&Watching::key(150)).unwrap();

        assert_eq!(row.comparison(), None);
    }
}

mod opening_the_comparison {
    use crate::application::actions::open_comparison::OpenComparison;
    use crate::application::queries::read_slice_detail::ReadSliceDetail;
    use crate::domain::comparison_opening::ComparisonOpening;
    use crate::domain::errors::ComparisonNotOpened;
    use crate::tests::application::watching::Watching;
    use crate::tests::doubles::RecordingOpener;
    use crate::tests::mothers::follow_line_mother::FollowLineMother;

    #[test]
    fn in_the_detail_of_a_slice_with_a_path_launches_open_with_that_path() {
        let watched = Watching::awaiting_merge_with_comparison();
        let (opener, calls) = RecordingOpener::succeeding();
        let detail = ReadSliceDetail::execute(Watching::key(150));

        let opening = OpenComparison::new(opener).execute(watched.board(), Some(&detail));

        assert_eq!(opening, ComparisonOpening::Opened);
        assert_eq!(*calls.lock().unwrap(), vec![FollowLineMother::COMPARISON.to_string()]);
    }

    #[test]
    fn in_the_detail_of_a_slice_without_a_path_launches_nothing() {
        let watched = Watching::one_tick(Watching::lines(vec![FollowLineMother::child_of(140, 150)]));
        let (opener, calls) = RecordingOpener::succeeding();
        let detail = ReadSliceDetail::execute(Watching::key(150));

        let opening = OpenComparison::new(opener).execute(watched.board(), Some(&detail));

        assert_eq!(opening, ComparisonOpening::Unavailable);
        assert!(calls.lock().unwrap().is_empty());
    }

    #[test]
    fn outside_the_detail_launches_nothing_even_if_the_slice_has_a_path() {
        let watched = Watching::awaiting_merge_with_comparison();
        let (opener, calls) = RecordingOpener::succeeding();

        let opening = OpenComparison::new(opener).execute(watched.board(), None);

        assert_eq!(opening, ComparisonOpening::Unavailable);
        assert!(calls.lock().unwrap().is_empty());
    }

    #[test]
    fn reports_a_failure_of_open_instead_of_propagating_it() {
        let watched = Watching::awaiting_merge_with_comparison();
        let (opener, _) = RecordingOpener::failing(ComparisonNotOpened::CommandFailed {
            reason: "exited with code 1".to_string(),
        });
        let detail = ReadSliceDetail::execute(Watching::key(150));

        let opening = OpenComparison::new(opener).execute(watched.board(), Some(&detail));

        assert_eq!(opening, ComparisonOpening::Failed);
    }
}
