mod the_transcripts_of_the_config_directory {
    use std::fs;
    use std::path::{Path, PathBuf};

    use crate::application::actions::reopen_workspace::{ReopenWorkspace, ReopenWorkspaceParams};
    use crate::infrastructure::config_dir_session_transcripts::ConfigDirSessionTranscripts;
    use crate::tests::doubles::ScriptedIssueSource;
    use crate::tests::mothers::workspace_mother::WorkspaceMother;

    struct Config {
        root: PathBuf,
    }

    impl Config {
        fn empty(name: &str) -> Self {
            let root = std::env::temp_dir().join(format!("{name}-{}", uuid::Uuid::new_v4()));
            fs::create_dir_all(&root).unwrap();

            Self { root }
        }

        fn with_transcript_for(&self, folder: &str) {
            let directory = self.root.join("projects").join(folder);
            fs::create_dir_all(&directory).unwrap();
            fs::write(directory.join(format!("{}.jsonl", WorkspaceMother::UUID)), "{}").unwrap();
        }

        fn argv_of_reopening(&self, directory: &Path) -> Vec<String> {
            let (source, _) = ScriptedIssueSource::answering(vec![Ok(WorkspaceMother::REPO.to_string())], vec![]);
            let source = source.with_bodies(vec![Ok(WorkspaceMother::body_marked_with(WorkspaceMother::UUID))]);

            ReopenWorkspace::new(source, ConfigDirSessionTranscripts::new(self.root.clone()))
                .execute(ReopenWorkspaceParams::new(directory.to_path_buf(), 516))
                .unwrap()
                .launch()
                .argv()
                .to_vec()
        }
    }

    impl Drop for Config {
        fn drop(&mut self) {
            fs::remove_dir_all(&self.root).ok();
        }
    }

    #[test]
    fn resumes_when_the_jsonl_of_the_directory_with_slashes_and_dots_turned_into_dashes_exists() {
        let config = Config::empty("transcripts-present");
        config.with_transcript_for("-work-my-repo--worktrees-04");

        let argv = config.argv_of_reopening(Path::new("/work/my.repo/.worktrees/04"));

        assert_eq!(argv, ["claude", "--resume", WorkspaceMother::UUID].map(str::to_string));
    }

    #[test]
    fn opens_a_new_session_when_there_is_no_jsonl() {
        let config = Config::empty("transcripts-absent");

        let argv = config.argv_of_reopening(Path::new("/work/my.repo"));

        assert_eq!(
            argv,
            ["claude", "--session-id", WorkspaceMother::UUID].map(str::to_string)
        );
    }

    #[test]
    fn a_transcript_kept_for_another_directory_does_not_count() {
        let config = Config::empty("transcripts-elsewhere");
        config.with_transcript_for("-work-other");

        let argv = config.argv_of_reopening(Path::new("/work/my.repo"));

        assert_eq!(
            argv,
            ["claude", "--session-id", WorkspaceMother::UUID].map(str::to_string)
        );
    }
}
