use ratatui::Terminal;
use ratatui::backend::TestBackend;

use crate::domain::update_availability::UpdateAvailability;
use crate::infrastructure::update_notice_view::UpdateNoticeView;

pub struct NoticeScreen;

impl NoticeScreen {
    pub fn text_of(availability: &UpdateAvailability) -> String {
        let mut terminal = Terminal::new(TestBackend::new(100, 1)).unwrap();
        terminal
            .draw(|frame| UpdateNoticeView::render(frame, frame.area(), availability))
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

mod the_update_notice_view {
    use crate::domain::update_availability::UpdateAvailability;
    use crate::infrastructure::update_notice_view::UpdateNoticeView;
    use crate::tests::infrastructure::update_notice_view::NoticeScreen;

    #[test]
    fn a_newer_version_is_announced_with_its_number_and_the_command_that_installs_it() {
        let screen = NoticeScreen::text_of(&UpdateAvailability::Newer("0.2.0".to_string()));

        assert!(screen.contains("0.2.0"), "{screen}");
        assert!(screen.contains("slice-runner update"), "{screen}");
    }

    #[test]
    fn without_a_newer_version_nothing_is_painted_and_no_row_is_taken() {
        let screen = NoticeScreen::text_of(&UpdateAvailability::Absent);

        assert!(screen.trim().is_empty(), "{screen}");
        assert_eq!(UpdateNoticeView::height_of(&UpdateAvailability::Absent), 0);
        assert_eq!(
            UpdateNoticeView::height_of(&UpdateAvailability::Newer("0.2.0".to_string())),
            1
        );
    }

    #[test]
    fn a_running_update_says_it_is_updating_to_the_version() {
        let screen = NoticeScreen::text_of(&UpdateAvailability::Updating("0.4.0".to_string()));

        assert_eq!(screen.trim(), "actualizando a 0.4.0...");
        assert!(screen.starts_with(" actualizando a 0.4.0..."), "{screen}");
    }

    #[test]
    fn an_installed_update_asks_to_reopen_to_use_it() {
        let screen = NoticeScreen::text_of(&UpdateAvailability::Installed("0.4.0".to_string()));

        assert!(screen.starts_with(" 0.4.0 instalada · reabre para usarla"), "{screen}");
        assert_eq!(screen.trim(), "0.4.0 instalada · reabre para usarla");
    }

    #[test]
    fn a_failed_update_says_why_and_which_command_retries_it() {
        let screen = NoticeScreen::text_of(&UpdateAvailability::Failed {
            version: "0.4.0".to_string(),
            reason: "salio con 1".to_string(),
        });

        assert!(
            screen.starts_with(" no se pudo actualizar a 0.4.0: salio con 1 · slice-runner update"),
            "{screen}"
        );
    }

    #[test]
    fn every_state_that_says_something_takes_one_row() {
        for availability in [
            UpdateAvailability::Updating("0.4.0".to_string()),
            UpdateAvailability::Installed("0.4.0".to_string()),
            UpdateAvailability::Failed {
                version: "0.4.0".to_string(),
                reason: "x".to_string(),
            },
        ] {
            assert_eq!(UpdateNoticeView::height_of(&availability), 1, "{availability:?}");
        }
    }
}
