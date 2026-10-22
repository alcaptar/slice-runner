mod the_threaded_update_check {
    use std::sync::mpsc::Sender;

    use crate::domain::update_availability::UpdateAvailability;
    use crate::infrastructure::threaded_update_check::ThreadedUpdateCheck;
    use crate::tests::doubles::GatedUpdateCheck;
    use crate::tests::waiting::Waiting;

    struct Gated;

    impl Gated {
        fn started() -> (ThreadedUpdateCheck, Sender<()>) {
            let (check, release) = GatedUpdateCheck::closed(UpdateAvailability::Newer("0.2.0".to_string()));

            (ThreadedUpdateCheck::start(check), release)
        }
    }

    #[test]
    fn with_a_check_that_does_not_answer_start_and_latest_return_at_once_and_nothing_is_announced() {
        let (mut check, _release) = Gated::started();

        assert_eq!(check.latest(), UpdateAvailability::Absent);
    }

    #[test]
    fn once_the_check_answers_latest_ends_up_delivering_the_newer_version_and_keeps_it() {
        let (mut check, release) = Gated::started();

        release.send(()).unwrap();

        let announced = Waiting::until(|| Some(check.latest()).filter(|found| *found != UpdateAvailability::Absent));
        assert_eq!(announced, UpdateAvailability::Newer("0.2.0".to_string()));
        assert_eq!(check.latest(), UpdateAvailability::Newer("0.2.0".to_string()));
    }
}
