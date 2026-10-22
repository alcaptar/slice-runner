use ratatui::layout::Rect;

use crate::infrastructure::slice_areas::SliceAreas;
use crate::tests::application::watching::Watching;

pub struct Windows;

pub struct Rows;

impl Rows {
    pub fn one_at_the_top_of_the_board() -> SliceAreas {
        SliceAreas::new(vec![(Watching::key(150), Rect::new(81, 6, 78, 1))])
    }
}

impl Windows {
    pub fn wide() -> Rect {
        Rect::new(0, 0, 160, 20)
    }
}

mod the_focus_given_by_a_click {
    use crate::infrastructure::key_routing::Focus;
    use crate::infrastructure::mouse_bytes::MouseBytes;
    use crate::infrastructure::mouse_routing::{MouseAction, MouseEffect, MouseRouting};
    use crate::infrastructure::slice_areas::SliceAreas;
    use crate::tests::infrastructure::mouse_bytes::MouseScreens;
    use crate::tests::infrastructure::mouse_routing::Windows;

    #[test]
    fn the_first_column_of_the_board_gives_it_the_focus() {
        let parser = MouseScreens::untouched();

        let action = MouseRouting::route(
            MouseScreens::left_down(80, 3),
            Windows::wide(),
            &mut MouseBytes::default(),
            parser.screen(),
            &SliceAreas::empty(),
        );

        assert_eq!(action, MouseAction::new(Some(Focus::Board), MouseEffect::Nothing));
    }

    #[test]
    fn the_right_border_of_the_claude_panel_gives_it_the_focus() {
        let parser = MouseScreens::untouched();

        let action = MouseRouting::route(
            MouseScreens::left_down(79, 3),
            Windows::wide(),
            &mut MouseBytes::default(),
            parser.screen(),
            &SliceAreas::empty(),
        );

        assert_eq!(action, MouseAction::new(Some(Focus::Claude), MouseEffect::Nothing));
    }

    #[test]
    fn a_click_inside_claude_gives_it_the_focus_and_still_reaches_it_as_bytes() {
        let parser = MouseScreens::with_sgr("1000");

        let action = MouseRouting::route(
            MouseScreens::left_down(5, 3),
            Windows::wide(),
            &mut MouseBytes::default(),
            parser.screen(),
            &SliceAreas::empty(),
        );

        assert_eq!(
            action,
            MouseAction::new(Some(Focus::Claude), MouseEffect::ToClaude(b"\x1b[<0;5;3M".to_vec()))
        );
    }
}

mod what_never_changes_the_focus {
    use crossterm::event::{MouseButton, MouseEventKind};

    use crate::infrastructure::mouse_bytes::MouseBytes;
    use crate::infrastructure::mouse_routing::{MouseAction, MouseEffect, MouseRouting};
    use crate::infrastructure::slice_areas::SliceAreas;
    use crate::tests::infrastructure::mouse_bytes::MouseScreens;
    use crate::tests::infrastructure::mouse_routing::Windows;

    #[test]
    fn the_wheel_over_claude_reaches_it_without_moving_the_focus() {
        let parser = MouseScreens::with_sgr("1000");

        let action = MouseRouting::route(
            MouseScreens::at(MouseEventKind::ScrollUp, 5, 3),
            Windows::wide(),
            &mut MouseBytes::default(),
            parser.screen(),
            &SliceAreas::empty(),
        );

        assert_eq!(
            action,
            MouseAction::new(None, MouseEffect::ToClaude(b"\x1b[<64;5;3M".to_vec()))
        );
    }

    #[test]
    fn the_wheel_over_the_board_does_nothing() {
        let parser = MouseScreens::with_sgr("1000");

        let action = MouseRouting::route(
            MouseScreens::at(MouseEventKind::ScrollUp, 90, 3),
            Windows::wide(),
            &mut MouseBytes::default(),
            parser.screen(),
            &SliceAreas::empty(),
        );

        assert_eq!(action, MouseAction::new(None, MouseEffect::Nothing));
    }

    #[test]
    fn a_drag_inside_claude_reaches_it_without_moving_the_focus() {
        let parser = MouseScreens::with_sgr("1002");
        let mut mouse = MouseBytes::default();
        MouseRouting::route(
            MouseScreens::left_down(5, 3),
            Windows::wide(),
            &mut mouse,
            parser.screen(),
            &SliceAreas::empty(),
        );

        let action = MouseRouting::route(
            MouseScreens::left_drag(6, 3),
            Windows::wide(),
            &mut mouse,
            parser.screen(),
            &SliceAreas::empty(),
        );

        assert_eq!(
            action,
            MouseAction::new(None, MouseEffect::ToClaude(b"\x1b[<32;6;3M".to_vec()))
        );
    }

    #[test]
    fn a_release_inside_claude_reaches_it_without_moving_the_focus() {
        let parser = MouseScreens::with_sgr("1002");
        let mut mouse = MouseBytes::default();
        MouseRouting::route(
            MouseScreens::left_down(5, 3),
            Windows::wide(),
            &mut mouse,
            parser.screen(),
            &SliceAreas::empty(),
        );

        let action = MouseRouting::route(
            MouseScreens::left_up(6, 3),
            Windows::wide(),
            &mut mouse,
            parser.screen(),
            &SliceAreas::empty(),
        );

        assert_eq!(
            action,
            MouseAction::new(None, MouseEffect::ToClaude(b"\x1b[<0;6;3m".to_vec()))
        );
    }

    #[test]
    fn a_release_over_the_board_after_pressing_in_claude_still_reaches_claude_at_its_edge() {
        let parser = MouseScreens::with_sgr("1000");
        let mut mouse = MouseBytes::default();
        MouseRouting::route(
            MouseScreens::left_down(5, 3),
            Windows::wide(),
            &mut mouse,
            parser.screen(),
            &SliceAreas::empty(),
        );

        let action = MouseRouting::route(
            MouseScreens::left_up(90, 3),
            Windows::wide(),
            &mut mouse,
            parser.screen(),
            &SliceAreas::empty(),
        );

        assert_eq!(
            action,
            MouseAction::new(None, MouseEffect::ToClaude(b"\x1b[<0;78;3m".to_vec()))
        );
    }

    #[test]
    fn the_right_button_over_the_board_does_nothing() {
        let parser = MouseScreens::with_sgr("1000");

        let action = MouseRouting::route(
            MouseScreens::at(MouseEventKind::Down(MouseButton::Right), 90, 3),
            Windows::wide(),
            &mut MouseBytes::default(),
            parser.screen(),
            &SliceAreas::empty(),
        );

        assert_eq!(action, MouseAction::new(None, MouseEffect::Nothing));
    }

    #[test]
    fn the_middle_button_over_the_board_does_nothing() {
        let parser = MouseScreens::with_sgr("1000");

        let action = MouseRouting::route(
            MouseScreens::at(MouseEventKind::Down(MouseButton::Middle), 90, 3),
            Windows::wide(),
            &mut MouseBytes::default(),
            parser.screen(),
            &SliceAreas::empty(),
        );

        assert_eq!(action, MouseAction::new(None, MouseEffect::Nothing));
    }
}

mod what_a_click_opens {
    use crossterm::event::MouseEventKind;

    use crate::infrastructure::key_routing::Focus;
    use crate::infrastructure::mouse_bytes::MouseBytes;
    use crate::infrastructure::mouse_routing::{MouseAction, MouseEffect, MouseRouting};
    use crate::tests::application::watching::Watching;
    use crate::tests::infrastructure::mouse_bytes::MouseScreens;
    use crate::tests::infrastructure::mouse_routing::{Rows, Windows};

    #[test]
    fn the_left_button_over_a_row_of_the_board_gives_it_the_focus_and_opens_its_slice() {
        let parser = MouseScreens::untouched();

        let action = MouseRouting::route(
            MouseScreens::left_down(90, 6),
            Windows::wide(),
            &mut MouseBytes::default(),
            parser.screen(),
            &Rows::one_at_the_top_of_the_board(),
        );

        assert_eq!(
            action,
            MouseAction::new(Some(Focus::Board), MouseEffect::Open(Watching::key(150)))
        );
    }

    #[test]
    fn the_left_button_over_the_board_where_there_is_no_row_gives_it_the_focus_and_opens_nothing() {
        let parser = MouseScreens::untouched();

        let action = MouseRouting::route(
            MouseScreens::left_down(90, 7),
            Windows::wide(),
            &mut MouseBytes::default(),
            parser.screen(),
            &Rows::one_at_the_top_of_the_board(),
        );

        assert_eq!(action, MouseAction::new(Some(Focus::Board), MouseEffect::Nothing));
    }

    #[test]
    fn the_wheel_over_a_row_of_the_board_neither_moves_the_focus_nor_opens_anything() {
        let parser = MouseScreens::untouched();

        let action = MouseRouting::route(
            MouseScreens::at(MouseEventKind::ScrollDown, 90, 6),
            Windows::wide(),
            &mut MouseBytes::default(),
            parser.screen(),
            &Rows::one_at_the_top_of_the_board(),
        );

        assert_eq!(action, MouseAction::new(None, MouseEffect::Nothing));
    }
}
