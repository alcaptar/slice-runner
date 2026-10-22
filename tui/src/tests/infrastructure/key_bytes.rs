use crossterm::event::{KeyCode, KeyEvent, KeyModifiers};
use vt100::Parser;

pub struct ChildScreens;

impl ChildScreens {
    pub fn plain() -> Parser {
        Parser::new(24, 80, 0)
    }

    pub fn with_application_cursor() -> Parser {
        Self::after(b"\x1b[?1h")
    }

    pub fn with_bracketed_paste() -> Parser {
        Self::after(b"\x1b[?2004h")
    }

    fn after(sequence: &[u8]) -> Parser {
        let mut parser = Self::plain();
        parser.process(sequence);

        parser
    }

    pub fn press(code: KeyCode) -> KeyEvent {
        KeyEvent::new(code, KeyModifiers::NONE)
    }

    pub fn press_with_alt(code: KeyCode) -> KeyEvent {
        KeyEvent::new(code, KeyModifiers::ALT)
    }

    pub fn press_with(code: KeyCode, modifiers: KeyModifiers) -> KeyEvent {
        KeyEvent::new(code, modifiers)
    }

    pub fn press_with_control(character: char) -> KeyEvent {
        KeyEvent::new(KeyCode::Char(character), KeyModifiers::CONTROL)
    }
}

mod the_bytes_of_a_key {
    use crossterm::event::{KeyCode, KeyModifiers};

    use crate::infrastructure::key_bytes::KeyBytes;
    use crate::tests::infrastructure::key_bytes::ChildScreens;

    #[test]
    fn escape_control_c_and_enter_are_their_single_bytes() {
        let parser = ChildScreens::plain();
        let screen = parser.screen();

        assert_eq!(KeyBytes::of(ChildScreens::press(KeyCode::Esc), screen), b"\x1b");
        assert_eq!(KeyBytes::of(ChildScreens::press_with_control('c'), screen), b"\x03");
        assert_eq!(KeyBytes::of(ChildScreens::press(KeyCode::Enter), screen), b"\r");
    }

    #[test]
    fn the_arrows_use_the_csi_form_in_normal_mode() {
        let parser = ChildScreens::plain();
        let screen = parser.screen();

        assert_eq!(KeyBytes::of(ChildScreens::press(KeyCode::Up), screen), b"\x1b[A");
        assert_eq!(KeyBytes::of(ChildScreens::press(KeyCode::Down), screen), b"\x1b[B");
        assert_eq!(KeyBytes::of(ChildScreens::press(KeyCode::Right), screen), b"\x1b[C");
        assert_eq!(KeyBytes::of(ChildScreens::press(KeyCode::Left), screen), b"\x1b[D");
    }

    #[test]
    fn the_arrows_use_the_ss3_form_once_the_child_asks_for_application_cursor_mode() {
        let parser = ChildScreens::with_application_cursor();
        let screen = parser.screen();

        assert_eq!(KeyBytes::of(ChildScreens::press(KeyCode::Up), screen), b"\x1bOA");
        assert_eq!(KeyBytes::of(ChildScreens::press(KeyCode::Down), screen), b"\x1bOB");
        assert_eq!(KeyBytes::of(ChildScreens::press(KeyCode::Right), screen), b"\x1bOC");
        assert_eq!(KeyBytes::of(ChildScreens::press(KeyCode::Left), screen), b"\x1bOD");
    }

    #[test]
    fn a_character_is_its_utf8_bytes() {
        let parser = ChildScreens::plain();

        assert_eq!(
            KeyBytes::of(ChildScreens::press(KeyCode::Char('ñ')), parser.screen()),
            "ñ".as_bytes()
        );
    }

    #[test]
    fn shift_tab_and_the_editing_keys_are_their_xterm_sequences() {
        let parser = ChildScreens::plain();
        let screen = parser.screen();

        assert_eq!(KeyBytes::of(ChildScreens::press(KeyCode::BackTab), screen), b"\x1b[Z");
        assert_eq!(KeyBytes::of(ChildScreens::press(KeyCode::Insert), screen), b"\x1b[2~");
        assert_eq!(KeyBytes::of(ChildScreens::press(KeyCode::Delete), screen), b"\x1b[3~");
        assert_eq!(KeyBytes::of(ChildScreens::press(KeyCode::PageUp), screen), b"\x1b[5~");
        assert_eq!(KeyBytes::of(ChildScreens::press(KeyCode::PageDown), screen), b"\x1b[6~");
    }

    #[test]
    fn home_and_end_follow_the_cursor_mode_the_child_asked_for() {
        let plain = ChildScreens::plain();
        let application = ChildScreens::with_application_cursor();

        assert_eq!(
            KeyBytes::of(ChildScreens::press(KeyCode::Home), plain.screen()),
            b"\x1b[H"
        );
        assert_eq!(
            KeyBytes::of(ChildScreens::press(KeyCode::End), plain.screen()),
            b"\x1b[F"
        );
        assert_eq!(
            KeyBytes::of(ChildScreens::press(KeyCode::Home), application.screen()),
            b"\x1bOH"
        );
        assert_eq!(
            KeyBytes::of(ChildScreens::press(KeyCode::End), application.screen()),
            b"\x1bOF"
        );
    }

    #[test]
    fn the_function_keys_are_their_xterm_sequences() {
        let parser = ChildScreens::plain();
        let screen = parser.screen();

        assert_eq!(KeyBytes::of(ChildScreens::press(KeyCode::F(1)), screen), b"\x1bOP");
        assert_eq!(KeyBytes::of(ChildScreens::press(KeyCode::F(4)), screen), b"\x1bOS");
        assert_eq!(KeyBytes::of(ChildScreens::press(KeyCode::F(5)), screen), b"\x1b[15~");
        assert_eq!(KeyBytes::of(ChildScreens::press(KeyCode::F(12)), screen), b"\x1b[24~");
    }

    #[test]
    fn alt_prefixes_the_bytes_of_the_key_with_escape() {
        let parser = ChildScreens::plain();
        let screen = parser.screen();

        assert_eq!(
            KeyBytes::of(ChildScreens::press_with_alt(KeyCode::Char('b')), screen),
            b"\x1bb"
        );
        assert_eq!(
            KeyBytes::of(ChildScreens::press_with_alt(KeyCode::Enter), screen),
            b"\x1b\r"
        );
    }

    #[test]
    fn super_backspace_deletes_the_line_as_control_u() {
        let parser = ChildScreens::plain();

        assert_eq!(
            KeyBytes::of(
                ChildScreens::press_with(KeyCode::Backspace, KeyModifiers::SUPER),
                parser.screen()
            ),
            b"\x15"
        );
    }

    #[test]
    fn alt_backspace_deletes_the_word_as_escape_then_delete() {
        let parser = ChildScreens::plain();

        assert_eq!(
            KeyBytes::of(ChildScreens::press_with_alt(KeyCode::Backspace), parser.screen()),
            b"\x1b\x7f"
        );
    }

    #[test]
    fn shift_enter_is_a_line_feed_while_a_plain_enter_stays_a_carriage_return() {
        let parser = ChildScreens::plain();
        let screen = parser.screen();

        assert_eq!(
            KeyBytes::of(ChildScreens::press_with(KeyCode::Enter, KeyModifiers::SHIFT), screen),
            b"\n"
        );
        assert_eq!(KeyBytes::of(ChildScreens::press(KeyCode::Enter), screen), b"\r");
    }

    #[test]
    fn backspace_with_no_modifier_or_with_control_is_the_delete_byte() {
        let parser = ChildScreens::plain();
        let screen = parser.screen();

        assert_eq!(KeyBytes::of(ChildScreens::press(KeyCode::Backspace), screen), b"\x7f");
        assert_eq!(
            KeyBytes::of(
                ChildScreens::press_with(KeyCode::Backspace, KeyModifiers::CONTROL),
                screen
            ),
            b"\x7f"
        );
    }

    #[test]
    fn non_ascii_characters_without_modifiers_are_their_utf8_bytes() {
        let parser = ChildScreens::plain();
        let screen = parser.screen();

        for character in ['é', 'ñ', '€'] {
            assert_eq!(
                KeyBytes::of(ChildScreens::press(KeyCode::Char(character)), screen),
                character.to_string().into_bytes()
            );
        }
    }

    #[test]
    fn a_key_with_no_translation_gives_no_bytes_even_with_alt() {
        let parser = ChildScreens::plain();
        let screen = parser.screen();

        assert!(KeyBytes::of(ChildScreens::press(KeyCode::F(13)), screen).is_empty());
        assert!(KeyBytes::of(ChildScreens::press_with_alt(KeyCode::CapsLock), screen).is_empty());
    }
}

mod the_bytes_of_a_paste {
    use crate::infrastructure::key_bytes::KeyBytes;
    use crate::tests::infrastructure::key_bytes::ChildScreens;

    #[test]
    fn are_wrapped_in_the_paste_markers_when_the_child_enabled_bracketed_paste() {
        let parser = ChildScreens::with_bracketed_paste();

        assert_eq!(KeyBytes::of_paste("a\nb", parser.screen()), b"\x1b[200~a\nb\x1b[201~");
    }

    #[test]
    fn are_typed_with_carriage_returns_when_the_child_did_not_enable_it() {
        let parser = ChildScreens::plain();

        assert_eq!(KeyBytes::of_paste("a\nb", parser.screen()), b"a\rb");
    }
}
