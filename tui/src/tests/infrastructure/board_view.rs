use std::path::PathBuf;

use ratatui::Terminal;
use ratatui::backend::TestBackend;
use ratatui::buffer::Buffer;
use ratatui::layout::Rect;
use ratatui::style::Color;

use crate::application::queries::read_slice_detail::SliceDetail;
use crate::application::queries::watch_slices::WatchedBoard;
use crate::domain::slice_key::SliceKey;
use crate::infrastructure::board_view::BoardView;
use crate::infrastructure::slice_areas::SliceAreas;
use crate::tests::mothers::screen_mother::ScreenMother;

pub struct Screen;

impl Screen {
    pub const WIDTH: u16 = 80;
    pub const HEIGHT: u16 = 24;

    pub fn captures_dir() -> Option<PathBuf> {
        std::env::var_os("CAPTURES_DIR").map(PathBuf::from)
    }

    pub fn text_of(watched: &WatchedBoard) -> String {
        Self::lines(&Self::painted(watched, None, None))
    }

    pub fn text_of_selecting(watched: &WatchedBoard, selected: &SliceKey, detail: Option<&SliceDetail>) -> String {
        Self::lines(&Self::painted(watched, Some(selected), detail))
    }

    pub fn painted(watched: &WatchedBoard, selected: Option<&SliceKey>, detail: Option<&SliceDetail>) -> Buffer {
        Self::painted_at(Self::WIDTH, watched, selected, detail)
    }

    pub fn painted_at(
        width: u16,
        watched: &WatchedBoard,
        selected: Option<&SliceKey>,
        detail: Option<&SliceDetail>,
    ) -> Buffer {
        Self::painted_with_focus(width, watched, selected, detail, false)
    }

    pub fn painted_with_focus(
        width: u16,
        watched: &WatchedBoard,
        selected: Option<&SliceKey>,
        detail: Option<&SliceDetail>,
        focused: bool,
    ) -> Buffer {
        let mut terminal = Terminal::new(TestBackend::new(width, Self::HEIGHT)).unwrap();
        terminal
            .draw(|frame| {
                BoardView::render(
                    frame,
                    frame.area(),
                    watched,
                    selected,
                    detail,
                    ScreenMother::NOW,
                    focused,
                );
            })
            .unwrap();

        terminal.backend().buffer().clone()
    }

    pub fn areas_of(area: Rect, watched: &WatchedBoard, detail: Option<&SliceDetail>) -> SliceAreas {
        let mut terminal = Terminal::new(TestBackend::new(area.right(), area.bottom())).unwrap();
        let mut areas = SliceAreas::empty();
        terminal
            .draw(|frame| {
                areas = BoardView::render(frame, area, watched, None, detail, ScreenMother::NOW, false);
            })
            .unwrap();

        areas
    }

    pub fn corner_colors(buffer: &Buffer) -> Vec<Color> {
        (0..buffer.area.height)
            .filter(|y| buffer[(0, *y)].symbol() == "┌")
            .map(|y| buffer[(0, y)].fg)
            .collect()
    }

    pub fn lines(buffer: &Buffer) -> String {
        let mut text = String::new();
        for y in 0..buffer.area.height {
            for x in 0..buffer.area.width {
                text.push_str(buffer[(x, y)].symbol());
            }
            text.push('\n');
        }
        text
    }

    pub fn color_of(buffer: &Buffer, text: &str) -> Vec<Color> {
        let mut colors = Vec::new();
        for y in 0..buffer.area.height {
            let row: Vec<&str> = (0..buffer.area.width).map(|x| buffer[(x, y)].symbol()).collect();
            let joined: String = row.concat();
            if let Some(byte) = joined.find(text) {
                let column = joined[..byte].chars().count();
                colors.push(buffer[(u16::try_from(column).unwrap(), y)].fg);
            }
        }
        colors
    }
}

mod the_tray {
    use ratatui::style::Color;

    use crate::tests::application::watching::Watching;
    use crate::tests::doubles::FixedProbe;
    use crate::tests::infrastructure::board_view::Screen;
    use crate::tests::infrastructure::screen_html::ScreenHtml;
    use crate::tests::mothers::screen_mother::ScreenMother;
    use crate::tests::mothers::workspace_mother::WorkspaceMother;

    #[test]
    fn paints_the_agreed_screen_character_by_character() {
        let watched = WorkspaceMother::showing(
            &Watching::entries(ScreenMother::feature(), FixedProbe::everyone_alive()),
            ScreenMother::PARENT,
        );

        let buffer = Screen::painted(&watched, Some(&ScreenMother::key(1)), None);
        ScreenHtml::write(Screen::captures_dir().as_deref(), "bandeja", &buffer);

        assert_eq!(Screen::lines(&buffer), include_str!("../screens/bandeja.txt"));
    }

    #[test]
    fn paints_each_glyph_with_its_colour_and_the_spend_near_the_budget_as_a_warning() {
        let watched = Watching::entries(ScreenMother::feature(), FixedProbe::everyone_alive());

        let buffer = Screen::painted(&watched, Some(&ScreenMother::key(1)), None);

        assert_eq!(Screen::color_of(&buffer, "◆"), vec![Color::Yellow]);
        assert_eq!(Screen::color_of(&buffer, "✕"), vec![Color::Red]);
        assert_eq!(Screen::color_of(&buffer, "◐"), vec![Color::Cyan, Color::Cyan]);
        assert_eq!(Screen::color_of(&buffer, "○"), vec![Color::DarkGray]);
        assert_eq!(Screen::color_of(&buffer, "✓"), vec![Color::Green]);
        assert_eq!(Screen::color_of(&buffer, "$42/50"), vec![Color::Yellow]);
    }

    #[test]
    fn shows_the_spend_from_eighty_percent_of_the_budget_and_not_below() {
        let at_the_edge = Watching::one_tick(Watching::lines(vec![ScreenMother::spending(40.0)]));
        let below = Watching::one_tick(Watching::lines(vec![ScreenMother::spending(39.99)]));

        assert!(Screen::text_of(&at_the_edge).contains("$40/50"));
        assert!(!Screen::text_of(&below).contains("$40/50"));
    }

    #[test]
    fn paints_the_last_action_under_a_running_slice_and_a_dead_process_among_what_needs_you() {
        let watched = WorkspaceMother::showing(
            &Watching::entries(
                ScreenMother::feature_with_activity(),
                FixedProbe::alive_only(&[ScreenMother::JUDGED_PID]),
            ),
            ScreenMother::PARENT,
        );

        let buffer = Screen::painted(&watched, Some(&ScreenMother::key(1)), None);

        ScreenHtml::write(Screen::captures_dir().as_deref(), "bandeja-con-actividad", &buffer);

        assert_eq!(
            Screen::lines(&buffer),
            include_str!("../screens/bandeja-con-actividad.txt")
        );
        assert_eq!(Screen::color_of(&buffer, "proceso muerto"), vec![Color::Red]);
    }
}

mod the_header_of_a_group {
    use crate::tests::application::watching::Watching;
    use crate::tests::doubles::FixedProbe;
    use crate::tests::infrastructure::board_view::Screen;
    use crate::tests::mothers::follow_line_mother::FollowLineMother;
    use crate::tests::mothers::screen_mother::ScreenMother;
    use crate::tests::mothers::workspace_mother::WorkspaceMother;

    struct Header;

    impl Header {
        fn border_of(text: &str) -> &str {
            text.lines().next().unwrap()
        }

        fn repo_line_of(text: &str) -> &str {
            text.lines().nth(1).unwrap()
        }
    }

    #[test]
    fn names_the_feature_by_its_number_and_its_title_and_how_many_slices_need_you() {
        let watched = WorkspaceMother::showing(
            &Watching::entries(ScreenMother::feature(), FixedProbe::everyone_alive()),
            ScreenMother::PARENT,
        );

        let screen = Screen::text_of(&watched);

        assert!(
            Header::border_of(&screen).starts_with("┌ #525 las slices dejan de abrir transacciones · 2 te necesitan ─"),
            "{screen}"
        );
    }

    #[test]
    fn says_one_slice_needs_you_in_the_singular() {
        let awaiting = FollowLineMother::awaiting_merge_with_comparison(&FollowLineMother::child_of(140, 150));
        let watched = WorkspaceMother::showing(&Watching::one_tick(Watching::lines(vec![awaiting])), 140);

        let screen = Screen::text_of(&watched);

        assert!(
            Header::border_of(&screen).starts_with("┌ #140 las slices dejan de abrir transacciones · 1 te necesita ─"),
            "{screen}"
        );
    }

    #[test]
    fn leaves_out_the_count_when_no_slice_needs_you() {
        let watched = WorkspaceMother::showing(
            &Watching::one_tick(Watching::lines(vec![FollowLineMother::child_of(140, 150)])),
            140,
        );

        let screen = Screen::text_of(&watched);

        assert!(
            Header::border_of(&screen).starts_with("┌ #140 las slices dejan de abrir transacciones ─"),
            "{screen}"
        );
    }

    #[test]
    fn keeps_the_border_of_today_for_a_workspace_without_a_title() {
        let watched = Watching::entries(ScreenMother::feature(), FixedProbe::everyone_alive());

        let screen = Screen::text_of(&watched);

        assert!(
            Header::border_of(&screen).starts_with("┌ alcaptar/demo-workspace #525 · 2 te necesitan ─"),
            "{screen}"
        );
    }

    #[test]
    fn cuts_a_title_that_does_not_fit_at_its_end_and_keeps_how_many_need_you_whole() {
        let watched = WorkspaceMother::showing(
            &Watching::entries(ScreenMother::feature(), FixedProbe::everyone_alive()),
            ScreenMother::PARENT,
        );

        let buffer = Screen::painted_at(58, &watched, None, None);
        let screen = Screen::lines(&buffer);

        assert_eq!(
            Header::border_of(&screen),
            "┌ #525 las slices dejan de abrir tran… · 2 te necesitan ─┐"
        );
    }

    #[test]
    fn puts_the_repo_on_the_left_and_the_slices_and_the_spend_on_the_right_under_the_border() {
        let watched = Watching::one_tick(Watching::lines(vec![
            ScreenMother::slice_spending(3, 1.20),
            ScreenMother::slice_spending(4, 1.90),
        ]));

        let screen = Screen::text_of(&watched);

        let line = Header::repo_line_of(&screen);
        assert!(line.starts_with("│ alcaptar/demo-workspace "), "{screen}");
        assert!(line.ends_with(" 2 slices · $3.10│"), "{screen}");
    }
}

mod the_tray_border {
    use ratatui::style::Color;

    use crate::tests::application::watching::Watching;
    use crate::tests::infrastructure::board_view::Screen;
    use crate::tests::mothers::follow_line_mother::FollowLineMother;

    #[test]
    fn paints_the_border_of_every_group_in_cyan_when_the_board_has_the_focus() {
        let watched = Watching::one_tick(Watching::lines(vec![
            FollowLineMother::orphan(170),
            FollowLineMother::child_of(140, 150),
        ]));

        let buffer = Screen::painted_with_focus(Screen::WIDTH, &watched, None, None, true);

        assert_eq!(Screen::corner_colors(&buffer), vec![Color::Cyan, Color::Cyan]);
    }

    #[test]
    fn paints_the_border_of_every_group_in_the_default_colour_without_the_focus() {
        let watched = Watching::one_tick(Watching::lines(vec![
            FollowLineMother::orphan(170),
            FollowLineMother::child_of(140, 150),
        ]));

        let buffer = Screen::painted_with_focus(Screen::WIDTH, &watched, None, None, false);

        assert_eq!(Screen::corner_colors(&buffer), vec![Color::Reset, Color::Reset]);
    }
}

mod the_tray_with_trouble {
    use crate::domain::errors::FollowLineRejected;
    use crate::tests::application::watching::Watching;
    use crate::tests::infrastructure::board_view::Screen;
    use crate::tests::mothers::follow_line_mother::FollowLineMother;

    #[test]
    fn paints_a_rejection_and_keeps_the_slices_on_screen() {
        let watched = Watching::one_tick(vec![
            Watching::lines(vec![FollowLineMother::child_of(140, 150)]).remove(0),
            Err(FollowLineRejected::UnsupportedVersion { version: 1 }),
        ]);

        let screen = Screen::text_of(&watched);

        assert!(screen.contains("unsupported follow line version 1"), "{screen}");
        assert!(screen.contains(FollowLineMother::NAME), "{screen}");
    }

    #[test]
    fn paints_nothing_about_errors_when_every_line_was_valid() {
        let watched = Watching::one_tick(Watching::lines(vec![FollowLineMother::orphan(170)]));

        assert!(!Screen::text_of(&watched).contains("unsupported"));
    }

    #[test]
    fn names_a_feature_without_parent_and_marks_only_the_selected_slice() {
        let watched = Watching::three_slices_in_two_groups();

        let screen = Screen::text_of_selecting(&watched, &Watching::key(160), None);

        assert!(screen.contains("alcaptar/demo-workspace sin padre"), "{screen}");
        assert_eq!(screen.matches('>').count(), 1, "{screen}");
    }
}

mod the_tray_with_an_open_detail {
    use ratatui::style::Color;

    use crate::application::queries::read_slice_detail::ReadSliceDetail;
    use crate::tests::application::watching::Watching;
    use crate::tests::doubles::FixedProbe;
    use crate::tests::infrastructure::board_view::Screen;
    use crate::tests::infrastructure::screen_html::ScreenHtml;
    use crate::tests::mothers::screen_mother::ScreenMother;
    use crate::tests::mothers::workspace_mother::WorkspaceMother;

    #[test]
    fn paints_the_detail_over_the_whole_board() {
        let watched = Watching::entries(ScreenMother::feature(), FixedProbe::everyone_alive());
        let detail = ReadSliceDetail::execute(ScreenMother::key(4));

        let buffer = Screen::painted(&watched, Some(&ScreenMother::key(4)), Some(&detail));
        ScreenHtml::write(Screen::captures_dir().as_deref(), "detalle-bloqueada", &buffer);

        assert_eq!(Screen::lines(&buffer), include_str!("../screens/detalle-bloqueada.txt"));
    }

    #[test]
    fn paints_the_detail_corner_in_cyan_when_the_board_has_the_focus() {
        let watched = Watching::entries(ScreenMother::feature(), FixedProbe::everyone_alive());
        let detail = ReadSliceDetail::execute(ScreenMother::key(4));

        let buffer = Screen::painted_with_focus(Screen::WIDTH, &watched, None, Some(&detail), true);

        assert_eq!(buffer[(0, 0)].fg, Color::Cyan);
    }

    #[test]
    fn paints_the_detail_corner_in_the_default_colour_without_the_focus() {
        let watched = Watching::entries(ScreenMother::feature(), FixedProbe::everyone_alive());
        let detail = ReadSliceDetail::execute(ScreenMother::key(4));

        let buffer = Screen::painted_with_focus(Screen::WIDTH, &watched, None, Some(&detail), false);

        assert_eq!(buffer[(0, 0)].fg, Color::Reset);
    }

    #[test]
    fn a_detail_for_a_slice_that_is_no_longer_on_the_board_paints_only_the_board() {
        let watched = WorkspaceMother::showing(
            &Watching::entries(ScreenMother::feature(), FixedProbe::everyone_alive()),
            ScreenMother::PARENT,
        );
        let detail = ReadSliceDetail::execute(Watching::key(999));

        let screen = Screen::text_of_selecting(&watched, &ScreenMother::key(1), Some(&detail));

        assert_eq!(screen, include_str!("../screens/bandeja.txt"));
    }
}

mod the_tray_with_several_features {
    use crate::domain::errors::FollowLineRejected;
    use crate::tests::application::watching::Watching;
    use crate::tests::infrastructure::board_view::Screen;
    use crate::tests::mothers::follow_line_mother::FollowLineMother;

    #[test]
    fn keeps_the_keys_and_the_rejection_on_screen_when_the_groups_fill_it() {
        let mut deliveries = Watching::lines(
            (0..12)
                .map(|issue| FollowLineMother::child_of(140 + issue, 150 + issue))
                .collect(),
        );
        deliveries.push(Err(FollowLineRejected::UnsupportedVersion { version: 3 }));
        let watched = Watching::one_tick(deliveries);

        let screen = Screen::text_of(&watched);

        assert!(screen.contains("unsupported follow line version 3"), "{screen}");
        assert!(screen.contains("enter detalle"), "{screen}");
    }
}

mod the_tray_at_the_width_of_half_a_laptop_screen {
    use crate::tests::application::watching::Watching;
    use crate::tests::doubles::FixedProbe;
    use crate::tests::infrastructure::board_view::Screen;
    use crate::tests::infrastructure::screen_html::ScreenHtml;
    use crate::tests::mothers::screen_mother::ScreenMother;
    use crate::tests::mothers::workspace_mother::WorkspaceMother;

    const NARROW: u16 = 58;

    #[test]
    fn keeps_every_summary_whole_by_shortening_the_names() {
        let watched = WorkspaceMother::showing(
            &Watching::entries(ScreenMother::feature(), FixedProbe::everyone_alive()),
            ScreenMother::PARENT,
        );

        let buffer = Screen::painted_at(NARROW, &watched, Some(&ScreenMother::key(1)), None);
        ScreenHtml::write(Screen::captures_dir().as_deref(), "bandeja-58", &buffer);

        assert_eq!(Screen::lines(&buffer), include_str!("../screens/bandeja-58.txt"));
    }
}

mod the_detail_at_the_width_of_half_a_laptop_screen {
    use crate::application::queries::read_slice_detail::ReadSliceDetail;
    use crate::tests::application::watching::Watching;
    use crate::tests::doubles::FixedProbe;
    use crate::tests::infrastructure::board_view::Screen;
    use crate::tests::infrastructure::screen_html::ScreenHtml;
    use crate::tests::mothers::screen_mother::ScreenMother;

    const NARROW: u16 = 58;

    #[test]
    fn breaks_the_command_to_reopen_and_keeps_each_duration_on_its_line() {
        let watched = Watching::entries(ScreenMother::feature(), FixedProbe::everyone_alive());
        let detail = ReadSliceDetail::execute(ScreenMother::key(4));

        let buffer = Screen::painted_at(NARROW, &watched, Some(&ScreenMother::key(4)), Some(&detail));
        ScreenHtml::write(Screen::captures_dir().as_deref(), "detalle-bloqueada-58", &buffer);

        assert_eq!(
            Screen::lines(&buffer),
            include_str!("../screens/detalle-bloqueada-58.txt")
        );
    }
}

mod the_slice_areas_of_the_tray {
    use ratatui::layout::Rect;

    use crate::application::queries::read_slice_detail::ReadSliceDetail;
    use crate::infrastructure::slice_areas::SliceAreas;
    use crate::tests::application::watching::Watching;
    use crate::tests::doubles::FixedProbe;
    use crate::tests::infrastructure::board_view::Screen;
    use crate::tests::mothers::screen_mother::ScreenMother;

    struct Placed;

    impl Placed {
        fn two_groups() -> Rect {
            Rect::new(80, 3, 80, 19)
        }

        fn with_activity() -> Rect {
            Rect::new(80, 3, 80, 24)
        }
    }

    #[test]
    fn name_the_slice_under_a_point_of_each_group() {
        let areas = Screen::areas_of(Placed::two_groups(), &Watching::three_slices_in_two_groups(), None);

        assert_eq!(areas.at(81, 7), Some(&Watching::key(150)));
        assert_eq!(areas.at(158, 13), Some(&Watching::key(160)));
        assert_eq!(areas.at(120, 19), Some(&Watching::key(170)));
    }

    #[test]
    fn give_each_row_the_interior_line_of_its_group_without_the_border_columns() {
        let areas = Screen::areas_of(Placed::two_groups(), &Watching::three_slices_in_two_groups(), None);

        assert_eq!(
            areas,
            SliceAreas::new(vec![
                (Watching::key(150), Rect::new(81, 7, 78, 1)),
                (Watching::key(160), Rect::new(81, 13, 78, 1)),
                (Watching::key(170), Rect::new(81, 19, 78, 1)),
            ])
        );
    }

    #[test]
    fn name_no_slice_over_an_attention_heading() {
        let areas = Screen::areas_of(Placed::two_groups(), &Watching::three_slices_in_two_groups(), None);

        assert_eq!(areas.at(90, 6), None);
    }

    #[test]
    fn name_no_slice_over_the_activity_line_of_a_running_slice() {
        let watched = Watching::entries(
            ScreenMother::feature_with_activity(),
            FixedProbe::alive_only(&[ScreenMother::JUDGED_PID]),
        );

        let areas = Screen::areas_of(Placed::with_activity(), &watched, None);

        assert_eq!(areas.at(90, 13), None);
        assert_eq!(areas.at(90, 12), Some(&ScreenMother::key(2)));
    }

    #[test]
    fn name_no_slice_over_the_side_border_of_a_group_at_the_height_of_a_row() {
        let areas = Screen::areas_of(Placed::two_groups(), &Watching::three_slices_in_two_groups(), None);

        assert_eq!(areas.at(80, 7), None);
        assert_eq!(areas.at(159, 7), None);
    }

    #[test]
    fn name_no_slice_over_the_bottom_border_of_a_group() {
        let areas = Screen::areas_of(Placed::two_groups(), &Watching::three_slices_in_two_groups(), None);

        assert_eq!(areas.at(90, 8), None);
        assert_eq!(areas.at(90, 20), None);
    }

    #[test]
    fn name_no_slice_over_the_footer() {
        let areas = Screen::areas_of(Placed::two_groups(), &Watching::three_slices_in_two_groups(), None);

        assert_eq!(areas.at(90, 21), None);
    }

    #[test]
    fn leave_out_the_rows_a_group_loses_below_its_bottom_border() {
        let area = Rect::new(80, 3, 80, 12);

        let areas = Screen::areas_of(area, &Watching::three_slices_in_two_groups(), None);

        assert_eq!(
            areas,
            SliceAreas::new(vec![(Watching::key(150), Rect::new(81, 7, 78, 1))])
        );
    }

    #[test]
    fn are_empty_while_the_detail_of_a_slice_on_the_board_is_painted() {
        let detail = ReadSliceDetail::execute(Watching::key(150));

        let areas = Screen::areas_of(
            Placed::two_groups(),
            &Watching::three_slices_in_two_groups(),
            Some(&detail),
        );

        assert_eq!(areas, SliceAreas::empty());
    }

    #[test]
    fn are_the_rows_of_the_list_when_the_detail_is_of_a_slice_no_longer_on_the_board() {
        let detail = ReadSliceDetail::execute(Watching::key(999));

        let areas = Screen::areas_of(
            Placed::two_groups(),
            &Watching::three_slices_in_two_groups(),
            Some(&detail),
        );

        assert_eq!(areas.at(81, 7), Some(&Watching::key(150)));
    }
}
