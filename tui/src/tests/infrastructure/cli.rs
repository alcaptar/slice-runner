mod the_version_flag {
    use std::path::PathBuf;

    use crate::infrastructure::cli::{Cli, Invocation};

    struct Arguments;

    impl Arguments {
        fn of(values: &[&str]) -> Vec<String> {
            values.iter().map(ToString::to_string).collect()
        }
    }

    #[test]
    fn it_is_requested_by_the_flag_alone() {
        assert_eq!(
            Cli::invocation_of(&Arguments::of(&["--version"])),
            Ok(Invocation::Version)
        );
    }

    #[test]
    fn it_is_not_requested_by_a_launch_without_arguments_or_with_a_parent_number() {
        assert_eq!(Cli::invocation_of(&Arguments::of(&[])), Ok(Invocation::Fresh));
        assert_eq!(Cli::invocation_of(&Arguments::of(&["12"])), Ok(Invocation::Reopen(12)));
    }

    #[test]
    fn the_flag_next_to_other_arguments_is_a_usage_error() {
        assert!(Cli::invocation_of(&Arguments::of(&["--version", "12"])).is_err());
    }

    #[test]
    fn the_version_it_reports_is_the_one_the_manifest_declares() {
        let manifest = std::fs::read_to_string(PathBuf::from(env!("CARGO_MANIFEST_DIR")).join("Cargo.toml")).unwrap();

        assert!(manifest.contains(&format!("\nversion = \"{}\"\n", Cli::VERSION)));
    }
}

mod the_background_update {
    use std::time::Duration;

    use crate::domain::auto_update::AutoUpdate;
    use crate::infrastructure::cli::Cli;

    #[test]
    fn the_entrypoint_gives_the_child_three_hundred_seconds() {
        assert_eq!(Cli::UPDATE_BUDGET, Duration::from_mins(5));
    }

    #[test]
    fn it_is_disabled_only_when_the_variable_is_exactly_one() {
        assert_eq!(Cli::auto_update_of(Some("1")), AutoUpdate::Disabled);
        for value in [None, Some(""), Some("0"), Some("true"), Some("11")] {
            assert_eq!(Cli::auto_update_of(value), AutoUpdate::Enabled, "{value:?}");
        }
    }
}
