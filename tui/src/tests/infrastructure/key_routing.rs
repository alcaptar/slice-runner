use crossterm::event::{KeyCode, KeyEvent, KeyEventKind, KeyEventState, KeyModifiers};

pub struct Keys;

impl Keys {
    pub fn press(code: KeyCode) -> KeyEvent {
        KeyEvent::new(code, KeyModifiers::NONE)
    }

    pub fn control_c() -> KeyEvent {
        KeyEvent::new(KeyCode::Char('c'), KeyModifiers::CONTROL)
    }

    pub fn control_q() -> KeyEvent {
        KeyEvent::new(KeyCode::Char('q'), KeyModifiers::CONTROL)
    }

    pub fn control_backslash() -> KeyEvent {
        KeyEvent::new(KeyCode::Char('4'), KeyModifiers::CONTROL)
    }

    pub fn control_backslash_with_the_keyboard_protocol() -> KeyEvent {
        KeyEvent::new(KeyCode::Char('\\'), KeyModifiers::CONTROL)
    }

    pub fn released(code: KeyCode) -> KeyEvent {
        KeyEvent::new_with_kind_and_state(code, KeyModifiers::NONE, KeyEventKind::Release, KeyEventState::NONE)
    }
}

mod with_the_focus_on_claude {
    use crossterm::event::KeyCode;
    use vt100::Parser;

    use crate::infrastructure::key_routing::{Focus, KeyRouting, Routed};
    use crate::tests::infrastructure::key_routing::Keys;

    #[test]
    fn q_control_c_and_the_arrows_only_go_to_claude() {
        let parser = Parser::new(24, 80, 0);
        let screen = parser.screen();

        assert_eq!(
            KeyRouting::route(Focus::Claude, Keys::press(KeyCode::Char('q')), screen),
            Routed::ToClaude(b"q".to_vec())
        );
        assert_eq!(
            KeyRouting::route(Focus::Claude, Keys::control_c(), screen),
            Routed::ToClaude(b"\x03".to_vec())
        );
        assert_eq!(
            KeyRouting::route(Focus::Claude, Keys::press(KeyCode::Up), screen),
            Routed::ToClaude(b"\x1b[A".to_vec())
        );
    }

    #[test]
    fn control_q_toggles_the_focus_and_is_never_forwarded() {
        let parser = Parser::new(24, 80, 0);

        assert_eq!(
            KeyRouting::route(Focus::Claude, Keys::control_q(), parser.screen()),
            Routed::ToggleFocus
        );
    }

    #[test]
    fn control_backslash_is_ignored_instead_of_toggling_or_reaching_claude() {
        let parser = Parser::new(24, 80, 0);

        assert_eq!(
            KeyRouting::route(Focus::Claude, Keys::control_backslash(), parser.screen()),
            Routed::Ignored
        );
    }

    #[test]
    fn control_backslash_as_the_keyboard_protocol_sends_it_is_ignored() {
        let parser = Parser::new(24, 80, 0);

        assert_eq!(
            KeyRouting::route(
                Focus::Claude,
                Keys::control_backslash_with_the_keyboard_protocol(),
                parser.screen()
            ),
            Routed::Ignored
        );
    }

    #[test]
    fn a_key_release_goes_nowhere() {
        let parser = Parser::new(24, 80, 0);

        assert_eq!(
            KeyRouting::route(Focus::Claude, Keys::released(KeyCode::Char('a')), parser.screen()),
            Routed::Ignored
        );
    }
}

mod with_the_focus_on_the_board {
    use crossterm::event::KeyCode;
    use vt100::Parser;

    use crate::infrastructure::key_routing::{Focus, KeyRouting, Order, Routed};
    use crate::tests::infrastructure::key_routing::Keys;

    #[test]
    fn q_and_control_c_close_the_interface() {
        let parser = Parser::new(24, 80, 0);
        let screen = parser.screen();

        assert_eq!(
            KeyRouting::route(Focus::Board, Keys::press(KeyCode::Char('q')), screen),
            Routed::Board(Order::Quit)
        );
        assert_eq!(
            KeyRouting::route(Focus::Board, Keys::control_c(), screen),
            Routed::Board(Order::Quit)
        );
    }

    #[test]
    fn the_arrows_and_enter_drive_the_board_and_nothing_reaches_claude() {
        let parser = Parser::new(24, 80, 0);
        let screen = parser.screen();

        assert_eq!(
            KeyRouting::route(Focus::Board, Keys::press(KeyCode::Down), screen),
            Routed::Board(Order::Next)
        );
        assert_eq!(
            KeyRouting::route(Focus::Board, Keys::press(KeyCode::Char('k')), screen),
            Routed::Board(Order::Previous)
        );
        assert_eq!(
            KeyRouting::route(Focus::Board, Keys::press(KeyCode::Enter), screen),
            Routed::Board(Order::Open)
        );
        assert_eq!(
            KeyRouting::route(Focus::Board, Keys::press(KeyCode::Char('x')), screen),
            Routed::Board(Order::Nothing)
        );
    }

    #[test]
    fn v_asks_to_open_the_comparison_and_only_with_the_focus_on_the_board() {
        let parser = Parser::new(24, 80, 0);
        let screen = parser.screen();

        assert_eq!(
            KeyRouting::route(Focus::Board, Keys::press(KeyCode::Char('v')), screen),
            Routed::Board(Order::OpenComparison)
        );
        assert_eq!(
            KeyRouting::route(Focus::Claude, Keys::press(KeyCode::Char('v')), screen),
            Routed::ToClaude(b"v".to_vec())
        );
    }

    #[test]
    fn control_q_toggles_the_focus_back_while_a_plain_q_still_quits() {
        let parser = Parser::new(24, 80, 0);
        let screen = parser.screen();

        assert_eq!(
            KeyRouting::route(Focus::Board, Keys::control_q(), screen),
            Routed::ToggleFocus
        );
        assert_eq!(
            KeyRouting::route(Focus::Board, Keys::press(KeyCode::Char('q')), screen),
            Routed::Board(Order::Quit)
        );
    }

    #[test]
    fn control_backslash_is_ignored() {
        let parser = Parser::new(24, 80, 0);

        assert_eq!(
            KeyRouting::route(Focus::Board, Keys::control_backslash(), parser.screen()),
            Routed::Ignored
        );
    }

    #[test]
    fn control_backslash_as_the_keyboard_protocol_sends_it_is_ignored_too() {
        let parser = Parser::new(24, 80, 0);

        assert_eq!(
            KeyRouting::route(
                Focus::Board,
                Keys::control_backslash_with_the_keyboard_protocol(),
                parser.screen()
            ),
            Routed::Ignored
        );
    }
}
