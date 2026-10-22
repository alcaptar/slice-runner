use crossterm::event::{KeyModifiers, MouseButton, MouseEvent, MouseEventKind};
use ratatui::layout::Rect;
use vt100::Parser;

pub struct MouseScreens;

impl MouseScreens {
    pub fn panel() -> Rect {
        Rect::new(0, 0, 80, 20)
    }

    pub fn with_sgr(mode: &str) -> Parser {
        Self::after(&format!("\x1b[?{mode}h\x1b[?1006h"))
    }

    pub fn with_mode_only(mode: &str) -> Parser {
        Self::after(&format!("\x1b[?{mode}h"))
    }

    pub fn untouched() -> Parser {
        Parser::new(24, 80, 0)
    }

    fn after(sequence: &str) -> Parser {
        let mut parser = Self::untouched();
        parser.process(sequence.as_bytes());

        parser
    }

    pub fn at(kind: MouseEventKind, column: u16, row: u16) -> MouseEvent {
        MouseEvent {
            kind,
            column,
            row,
            modifiers: KeyModifiers::NONE,
        }
    }

    pub fn left_down(column: u16, row: u16) -> MouseEvent {
        Self::at(MouseEventKind::Down(MouseButton::Left), column, row)
    }

    pub fn left_drag(column: u16, row: u16) -> MouseEvent {
        Self::at(MouseEventKind::Drag(MouseButton::Left), column, row)
    }

    pub fn left_up(column: u16, row: u16) -> MouseEvent {
        Self::at(MouseEventKind::Up(MouseButton::Left), column, row)
    }
}

mod the_bytes_of_a_mouse_event {
    use crossterm::event::{MouseButton, MouseEventKind};

    use crate::infrastructure::mouse_bytes::MouseBytes;
    use crate::tests::infrastructure::mouse_bytes::MouseScreens;

    const ANY_BUTTON_MOTION: &str = "1002";
    const PRESS_RELEASE: &str = "1000";
    const PRESS_ONLY: &str = "9";
    const ANY_MOTION: &str = "1003";

    #[test]
    fn the_wheel_up_is_forwarded_in_sgr_with_one_based_coordinates_inside_the_border() {
        let parser = MouseScreens::with_sgr(PRESS_RELEASE);
        let event = MouseScreens::at(MouseEventKind::ScrollUp, 5, 3);

        let bytes = MouseBytes::default().of(event, MouseScreens::panel(), parser.screen());

        assert_eq!(bytes, b"\x1b[<64;5;3M");
    }

    #[test]
    fn the_wheel_down_is_forwarded_as_sixty_five() {
        let parser = MouseScreens::with_sgr(PRESS_RELEASE);
        let event = MouseScreens::at(MouseEventKind::ScrollDown, 5, 3);

        let bytes = MouseBytes::default().of(event, MouseScreens::panel(), parser.screen());

        assert_eq!(bytes, b"\x1b[<65;5;3M");
    }

    #[test]
    fn pressing_the_left_button_is_forwarded_as_a_press() {
        let parser = MouseScreens::with_sgr(PRESS_RELEASE);

        let bytes = MouseBytes::default().of(MouseScreens::left_down(5, 3), MouseScreens::panel(), parser.screen());

        assert_eq!(bytes, b"\x1b[<0;5;3M");
    }

    #[test]
    fn dragging_the_left_button_is_forwarded_as_thirty_two() {
        let parser = MouseScreens::with_sgr(ANY_BUTTON_MOTION);
        let mut mouse = MouseBytes::default();
        mouse.of(MouseScreens::left_down(5, 3), MouseScreens::panel(), parser.screen());

        let bytes = mouse.of(MouseScreens::left_drag(5, 3), MouseScreens::panel(), parser.screen());

        assert_eq!(bytes, b"\x1b[<32;5;3M");
    }

    #[test]
    fn releasing_the_left_button_is_forwarded_with_a_lowercase_m() {
        let parser = MouseScreens::with_sgr(PRESS_RELEASE);

        let bytes = MouseBytes::default().of(MouseScreens::left_up(5, 3), MouseScreens::panel(), parser.screen());

        assert_eq!(bytes, b"\x1b[<0;5;3m");
    }

    #[test]
    fn dragging_is_forwarded_with_button_motion_and_with_any_motion() {
        for mode in [ANY_BUTTON_MOTION, ANY_MOTION] {
            let parser = MouseScreens::with_sgr(mode);

            let bytes = MouseBytes::default().of(MouseScreens::left_drag(5, 3), MouseScreens::panel(), parser.screen());

            assert_eq!(bytes, b"\x1b[<32;5;3M");
        }
    }

    #[test]
    fn dragging_is_not_forwarded_with_press_release() {
        let parser = MouseScreens::with_sgr(PRESS_RELEASE);

        let bytes = MouseBytes::default().of(MouseScreens::left_drag(5, 3), MouseScreens::panel(), parser.screen());

        assert!(bytes.is_empty());
    }

    #[test]
    fn the_press_mode_forwards_nothing() {
        let parser = MouseScreens::with_sgr(PRESS_ONLY);
        let mut mouse = MouseBytes::default();
        let events = [
            MouseScreens::left_down(5, 3),
            MouseScreens::left_drag(5, 3),
            MouseScreens::left_up(5, 3),
            MouseScreens::at(MouseEventKind::ScrollUp, 5, 3),
        ];

        for event in events {
            assert!(mouse.of(event, MouseScreens::panel(), parser.screen()).is_empty());
        }
    }

    #[test]
    fn a_release_outside_the_panel_after_a_press_inside_is_pinned_to_the_inner_edge() {
        let parser = MouseScreens::with_sgr(PRESS_RELEASE);
        let mut mouse = MouseBytes::default();
        mouse.of(MouseScreens::left_down(5, 3), MouseScreens::panel(), parser.screen());

        let bytes = mouse.of(MouseScreens::left_up(90, 3), MouseScreens::panel(), parser.screen());

        assert_eq!(bytes, b"\x1b[<0;78;3m");
    }

    #[test]
    fn a_drag_below_the_panel_after_a_press_inside_is_pinned_to_the_last_inner_row() {
        let parser = MouseScreens::with_sgr(ANY_BUTTON_MOTION);
        let mut mouse = MouseBytes::default();
        mouse.of(MouseScreens::left_down(5, 3), MouseScreens::panel(), parser.screen());

        let bytes = mouse.of(MouseScreens::left_drag(2, 40), MouseScreens::panel(), parser.screen());

        assert_eq!(bytes, b"\x1b[<32;2;18M");
    }

    #[test]
    fn after_the_release_an_event_outside_is_forwarded_no_more() {
        let parser = MouseScreens::with_sgr(PRESS_RELEASE);
        let mut mouse = MouseBytes::default();
        mouse.of(MouseScreens::left_down(5, 3), MouseScreens::panel(), parser.screen());
        mouse.of(MouseScreens::left_up(5, 3), MouseScreens::panel(), parser.screen());

        let bytes = mouse.of(MouseScreens::left_up(90, 3), MouseScreens::panel(), parser.screen());

        assert!(bytes.is_empty());
    }

    #[test]
    fn a_press_outside_the_panel_does_not_make_a_later_release_outside_forwardable() {
        let parser = MouseScreens::with_sgr(PRESS_RELEASE);
        let mut mouse = MouseBytes::default();
        mouse.of(MouseScreens::left_down(90, 3), MouseScreens::panel(), parser.screen());

        let bytes = mouse.of(MouseScreens::left_up(90, 3), MouseScreens::panel(), parser.screen());

        assert!(bytes.is_empty());
    }

    #[test]
    fn without_a_mouse_mode_nothing_is_forwarded() {
        let parser = MouseScreens::untouched();

        let bytes = MouseBytes::default().of(MouseScreens::left_down(5, 3), MouseScreens::panel(), parser.screen());

        assert!(bytes.is_empty());
    }

    #[test]
    fn without_the_sgr_encoding_nothing_is_forwarded() {
        let parser = MouseScreens::with_mode_only(PRESS_RELEASE);

        let bytes = MouseBytes::default().of(MouseScreens::left_down(5, 3), MouseScreens::panel(), parser.screen());

        assert!(bytes.is_empty());
    }

    #[test]
    fn an_event_on_the_border_of_the_panel_is_not_forwarded() {
        let parser = MouseScreens::with_sgr(PRESS_RELEASE);

        let bytes = MouseBytes::default().of(MouseScreens::left_down(0, 3), MouseScreens::panel(), parser.screen());

        assert!(bytes.is_empty());
    }

    #[test]
    fn an_event_on_the_board_half_is_not_forwarded() {
        let parser = MouseScreens::with_sgr(PRESS_RELEASE);
        let event = MouseScreens::at(MouseEventKind::ScrollUp, 120, 3);

        let bytes = MouseBytes::default().of(event, MouseScreens::panel(), parser.screen());

        assert!(bytes.is_empty());
    }

    #[test]
    fn the_right_and_middle_buttons_are_not_forwarded() {
        let parser = MouseScreens::with_sgr(ANY_BUTTON_MOTION);
        let mut mouse = MouseBytes::default();
        mouse.of(MouseScreens::left_down(5, 3), MouseScreens::panel(), parser.screen());

        for button in [MouseButton::Right, MouseButton::Middle] {
            for kind in [
                MouseEventKind::Down(button),
                MouseEventKind::Drag(button),
                MouseEventKind::Up(button),
            ] {
                let event = MouseScreens::at(kind, 5, 3);

                assert!(mouse.of(event, MouseScreens::panel(), parser.screen()).is_empty());
            }
        }
    }

    #[test]
    fn motion_without_a_button_is_not_forwarded_in_any_mode() {
        for mode in [PRESS_RELEASE, ANY_BUTTON_MOTION, ANY_MOTION] {
            let parser = MouseScreens::with_sgr(mode);
            let event = MouseScreens::at(MouseEventKind::Moved, 5, 3);

            assert!(
                MouseBytes::default()
                    .of(event, MouseScreens::panel(), parser.screen())
                    .is_empty()
            );
        }
    }
}
