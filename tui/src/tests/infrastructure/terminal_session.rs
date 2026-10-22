pub struct Sequences;

impl Sequences {
    pub fn on_open() -> Vec<u8> {
        let mut out = Vec::new();
        crate::infrastructure::terminal_session::TerminalSession::write_open_sequence(&mut out).ok();

        out
    }

    pub fn on_close() -> Vec<u8> {
        let mut out = Vec::new();
        crate::infrastructure::terminal_session::TerminalSession::write_close_sequence(&mut out).ok();

        out
    }

    pub fn contain(written: &[u8], needle: &str) -> bool {
        written.windows(needle.len()).any(|window| window == needle.as_bytes())
    }
}

mod the_terminal_session_sequences {
    use crate::tests::infrastructure::terminal_session::Sequences;

    #[test]
    fn opening_asks_for_the_mouse_with_buttons_drag_and_sgr_and_never_for_all_motion() {
        let written = Sequences::on_open();

        assert!(Sequences::contain(&written, "\x1b[?1000h\x1b[?1002h\x1b[?1006h"));
        assert!(!Sequences::contain(&written, "?1003"));
    }

    #[test]
    fn opening_asks_for_the_kitty_keyboard_protocol_with_only_disambiguate_escape_codes() {
        let written = Sequences::on_open();

        assert!(Sequences::contain(&written, "\x1b[>1u"));
    }

    #[test]
    fn closing_pops_the_kitty_keyboard_flags() {
        let written = Sequences::on_close();

        assert!(Sequences::contain(&written, "\x1b[<1u"));
    }

    #[test]
    fn closing_gives_the_mouse_back_in_the_reverse_order_and_never_mentions_all_motion() {
        let written = Sequences::on_close();

        assert!(Sequences::contain(&written, "\x1b[?1006l\x1b[?1002l\x1b[?1000l"));
        assert!(!Sequences::contain(&written, "?1003"));
    }
}
