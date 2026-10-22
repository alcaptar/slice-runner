use ratatui::Terminal;
use ratatui::backend::TestBackend;
use ratatui::buffer::Buffer;

use crate::application::queries::read_slice_detail::{ReadSliceDetail, SliceDetail};
use crate::domain::comparison_opening::ComparisonOpening;
use crate::domain::slice_row::SliceRow;
use crate::infrastructure::detail_view::DetailView;
use crate::tests::infrastructure::board_view::Screen;
use crate::tests::mothers::screen_mother::ScreenMother;

pub struct DetailScreen;

impl DetailScreen {
    pub fn painted(row: &SliceRow) -> Buffer {
        Self::painted_with(row, &ReadSliceDetail::execute(row.key().clone()))
    }

    pub fn painted_with(row: &SliceRow, detail: &SliceDetail) -> Buffer {
        let mut terminal = Terminal::new(TestBackend::new(Screen::WIDTH, Screen::HEIGHT)).unwrap();
        terminal
            .draw(|frame| DetailView::render(frame, frame.area(), row, detail, ScreenMother::NOW, false))
            .unwrap();

        terminal.backend().buffer().clone()
    }

    pub fn text_of(row: &SliceRow) -> String {
        Screen::lines(&Self::painted(row))
    }

    pub fn text_after(row: &SliceRow, opening: ComparisonOpening) -> String {
        Screen::lines(&Self::painted_with(
            row,
            &ReadSliceDetail::execute(row.key().clone()).after(opening),
        ))
    }
}

mod the_detail_view {
    use crate::tests::application::watching::Watching;
    use crate::tests::doubles::FixedProbe;
    use crate::tests::infrastructure::board_view::Screen;
    use crate::tests::infrastructure::detail_view::DetailScreen;
    use crate::tests::infrastructure::screen_html::ScreenHtml;
    use crate::tests::mothers::screen_mother::ScreenMother;

    #[test]
    fn of_a_running_slice_shows_what_the_judge_is_doing_and_its_history_character_by_character() {
        let watched = Watching::entries(
            ScreenMother::feature_with_activity(),
            FixedProbe::alive_only(&[ScreenMother::JUDGED_PID, ScreenMother::IMPLEMENTED_PID]),
        );
        let row = watched.board().row(&ScreenMother::key(2)).unwrap();

        let buffer = DetailScreen::painted(row);
        ScreenHtml::write(Screen::captures_dir().as_deref(), "detalle-en-curso", &buffer);

        assert_eq!(Screen::lines(&buffer), include_str!("../screens/detalle-en-curso.txt"));
    }

    #[test]
    fn of_a_slice_with_a_round_without_changes_says_so_in_its_history() {
        let watched = Watching::one_tick(Watching::lines(ScreenMother::a_round_without_changes()));
        let row = watched.board().row(&ScreenMother::key(7)).unwrap();

        let screen = DetailScreen::text_of(row);

        assert!(screen.contains("implementa, vuelta 1, sin cambios"), "{screen}");
        assert!(screen.contains("implementa, vuelta 1     "), "{screen}");
    }

    #[test]
    fn of_a_running_slice_does_not_offer_to_reopen_it() {
        let watched = Watching::entries(ScreenMother::feature(), FixedProbe::everyone_alive());
        let row = watched.board().row(&ScreenMother::key(2)).unwrap();

        assert!(!DetailScreen::text_of(row).contains("slice-runner retry"));
    }
}

mod the_detail_view_of_a_long_story {
    use crate::tests::application::watching::Watching;
    use crate::tests::infrastructure::detail_view::DetailScreen;
    use crate::tests::mothers::screen_mother::ScreenMother;

    #[test]
    fn keeps_the_command_to_reopen_and_drops_the_oldest_steps() {
        let watched = Watching::one_tick(Watching::lines(ScreenMother::a_long_blocked_story()));
        let row = watched.board().row(&ScreenMother::key(8)).unwrap();

        let screen = DetailScreen::text_of(row);

        assert!(screen.contains("slice-runner retry 533"), "{screen}");
        assert!(screen.contains("bloqueada: controles"), "{screen}");
        assert!(!screen.contains("hace 40m"), "{screen}");
    }
}

mod the_detail_view_of_a_slice_with_a_comparison {
    use crate::domain::comparison_opening::ComparisonOpening;
    use crate::tests::application::watching::Watching;
    use crate::tests::infrastructure::detail_view::DetailScreen;

    const OFFER: &str = "v comparación";
    const FAILURE: &str = "no se pudo abrir la comparación";

    #[test]
    fn offers_v_in_the_keys_bar() {
        let watched = Watching::awaiting_merge_with_comparison();
        let row = watched.board().row(&Watching::key(150)).unwrap();

        let screen = DetailScreen::text_of(row);

        assert!(screen.contains(OFFER), "{screen}");
        assert!(!screen.contains(FAILURE), "{screen}");
    }

    #[test]
    fn says_the_comparison_could_not_be_opened_after_a_failed_opening() {
        let watched = Watching::awaiting_merge_with_comparison();
        let row = watched.board().row(&Watching::key(150)).unwrap();

        let screen = DetailScreen::text_after(row, ComparisonOpening::Failed);

        assert!(screen.contains(FAILURE), "{screen}");
        assert!(screen.contains(OFFER), "{screen}");
    }

    #[test]
    fn stops_saying_it_once_a_later_opening_succeeds() {
        let watched = Watching::awaiting_merge_with_comparison();
        let row = watched.board().row(&Watching::key(150)).unwrap();

        let screen = DetailScreen::text_after(row, ComparisonOpening::Opened);

        assert!(!screen.contains(FAILURE), "{screen}");
    }
}

mod the_detail_view_of_a_slice_without_a_comparison {
    use crate::tests::application::watching::Watching;
    use crate::tests::infrastructure::detail_view::DetailScreen;
    use crate::tests::mothers::follow_line_mother::FollowLineMother;

    #[test]
    fn does_not_offer_v() {
        let watched = Watching::one_tick(Watching::lines(vec![FollowLineMother::child_of(140, 150)]));
        let row = watched.board().row(&Watching::key(150)).unwrap();

        assert!(!DetailScreen::text_of(row).contains("v comparación"));
    }
}
