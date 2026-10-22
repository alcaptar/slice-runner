mod updating_in_the_background {
    use crate::application::actions::update_in_background::UpdateInBackground;
    use crate::domain::auto_update::AutoUpdate;
    use crate::domain::update_availability::UpdateAvailability;
    use crate::domain::update_progress::UpdateProgress;
    use crate::tests::doubles::{FixedUpdateCheck, Launches, ScriptedProgramUpdate};

    struct Notice;

    impl Notice {
        fn with(
            availability: UpdateAvailability,
            auto_update: AutoUpdate,
            progress: UpdateProgress,
        ) -> (UpdateInBackground<FixedUpdateCheck, ScriptedProgramUpdate>, Launches) {
            let (update, launches) = ScriptedProgramUpdate::reporting(progress);

            (
                UpdateInBackground::new(FixedUpdateCheck::answering(availability), update, auto_update),
                launches,
            )
        }

        fn newer(
            auto_update: AutoUpdate,
            progress: UpdateProgress,
        ) -> (UpdateInBackground<FixedUpdateCheck, ScriptedProgramUpdate>, Launches) {
            Self::with(UpdateAvailability::Newer("0.4.0".to_string()), auto_update, progress)
        }
    }

    #[test]
    fn asking_the_notice_three_times_launches_the_update_exactly_once() {
        let (mut notice, launches) = Notice::newer(AutoUpdate::Enabled, UpdateProgress::Running);

        for _ in 0..3 {
            notice.execute();
        }

        assert_eq!(*launches.lock().unwrap(), vec!["0.4.0".to_string()]);
    }

    #[test]
    fn while_the_child_runs_the_notice_says_it_is_updating() {
        let (mut notice, _) = Notice::newer(AutoUpdate::Enabled, UpdateProgress::Running);

        assert_eq!(notice.execute(), UpdateAvailability::Updating("0.4.0".to_string()));
        assert_eq!(notice.execute(), UpdateAvailability::Updating("0.4.0".to_string()));
    }

    #[test]
    fn a_child_that_installed_leaves_the_notice_installed() {
        let (mut notice, _) = Notice::newer(AutoUpdate::Enabled, UpdateProgress::Installed);

        notice.execute();

        assert_eq!(notice.execute(), UpdateAvailability::Installed("0.4.0".to_string()));
    }

    #[test]
    fn a_child_that_failed_leaves_the_notice_failed_with_its_reason() {
        let (mut notice, _) = Notice::newer(AutoUpdate::Enabled, UpdateProgress::Failed("boom".to_string()));

        notice.execute();

        assert_eq!(
            notice.execute(),
            UpdateAvailability::Failed {
                version: "0.4.0".to_string(),
                reason: "boom".to_string()
            }
        );
    }

    #[test]
    fn with_the_automatic_update_disabled_nothing_is_launched_and_the_newer_version_is_announced() {
        let (mut notice, launches) = Notice::newer(AutoUpdate::Disabled, UpdateProgress::Running);

        for _ in 0..3 {
            assert_eq!(notice.execute(), UpdateAvailability::Newer("0.4.0".to_string()));
        }

        assert!(launches.lock().unwrap().is_empty());
    }

    #[test]
    fn without_a_newer_version_nothing_is_launched_and_nothing_is_announced() {
        let (mut notice, launches) =
            Notice::with(UpdateAvailability::Absent, AutoUpdate::Enabled, UpdateProgress::Running);

        assert_eq!(notice.execute(), UpdateAvailability::Absent);
        assert!(launches.lock().unwrap().is_empty());
    }
}
