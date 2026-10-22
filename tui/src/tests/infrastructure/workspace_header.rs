use ratatui::Terminal;
use ratatui::backend::TestBackend;

use crate::application::queries::bind_workspace::WorkspaceState;
use crate::infrastructure::workspace_header::WorkspaceHeader;

pub struct HeaderScreen;

impl HeaderScreen {
    pub fn text_of(state: &WorkspaceState) -> String {
        let mut terminal = Terminal::new(TestBackend::new(100, 3)).unwrap();
        terminal
            .draw(|frame| WorkspaceHeader::render(frame, frame.area(), state))
            .unwrap();

        terminal
            .backend()
            .buffer()
            .content()
            .iter()
            .map(ratatui::buffer::Cell::symbol)
            .collect()
    }
}

mod the_workspace_header {
    use crate::domain::errors::IssuesUnread;
    use crate::tests::application::bind_workspace::Binding;
    use crate::tests::infrastructure::workspace_header::HeaderScreen;
    use crate::tests::mothers::workspace_mother::WorkspaceMother;

    #[test]
    fn before_the_repo_is_known_says_so_and_shows_the_workspace_id_and_that_there_is_no_feature_yet() {
        let screen = HeaderScreen::text_of(&WorkspaceMother::unbound());

        assert!(screen.contains(WorkspaceMother::UUID), "{screen}");
        assert!(screen.contains("repo unknown"), "{screen}");
        assert!(screen.contains("no feature yet"), "{screen}");
    }

    #[test]
    fn bound_shows_the_repo_the_id_and_the_parent_and_not_the_missing_feature_line() {
        let screen = HeaderScreen::text_of(&WorkspaceMother::bound_to(140));

        assert!(screen.contains(WorkspaceMother::REPO), "{screen}");
        assert!(screen.contains(WorkspaceMother::UUID), "{screen}");
        assert!(screen.contains("feature #140"), "{screen}");
        assert!(!screen.contains("no feature yet"), "{screen}");
        assert!(!screen.contains("repo unknown"), "{screen}");
    }

    #[test]
    fn a_warning_of_gh_is_painted() {
        let (mut bind, _, _) = Binding::asking(
            vec![Err(IssuesUnread::CommandFailed {
                reason: "gh is not authenticated".to_string(),
            })],
            vec![],
        );

        let screen = HeaderScreen::text_of(&bind.execute());

        assert!(screen.contains("gh failed: gh is not authenticated"), "{screen}");
    }

    #[test]
    fn paints_no_warning_when_every_read_went_well() {
        let screen = HeaderScreen::text_of(&WorkspaceMother::bound_to(140));

        assert!(!screen.contains("gh "), "{screen}");
    }
}
