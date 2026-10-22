use crate::infrastructure::frame_holding_terminal::FrameHoldingTerminal;
use crate::tests::doubles::SteppedClock;

pub struct Frames;

impl Frames {
    pub fn terminal() -> (FrameHoldingTerminal, SteppedClock) {
        let clock = SteppedClock::standing_still();

        (FrameHoldingTerminal::new(24, 80, 0, clock.clone()), clock)
    }

    pub fn painted_text(terminal: &FrameHoldingTerminal) -> String {
        terminal.painted().contents()
    }

    pub fn live_text(terminal: &FrameHoldingTerminal) -> String {
        terminal.live().contents()
    }
}

mod an_open_frame {
    use std::time::Duration;

    use crate::tests::infrastructure::frame_holding_terminal::Frames;

    #[test]
    fn keeps_painting_the_screen_from_before_it_opened() {
        let (mut terminal, _clock) = Frames::terminal();
        terminal.process(b"before");

        terminal.process(b"\x1b[?2026h");
        terminal.process(b" after");

        assert_eq!(Frames::painted_text(&terminal), "before");
        assert_eq!(Frames::live_text(&terminal), "before after");
    }

    #[test]
    fn paints_the_new_text_as_soon_as_it_closes() {
        let (mut terminal, _clock) = Frames::terminal();
        terminal.process(b"before\x1b[?2026h after");

        terminal.process(b"\x1b[?2026l");

        assert_eq!(Frames::painted_text(&terminal), "before after");
    }

    #[test]
    fn is_still_held_after_199_milliseconds() {
        let (mut terminal, clock) = Frames::terminal();
        terminal.process(b"before\x1b[?2026h after");

        clock.advance(Duration::from_millis(199));

        assert_eq!(Frames::painted_text(&terminal), "before");
    }

    #[test]
    fn is_released_at_200_milliseconds_even_if_half_written() {
        let (mut terminal, clock) = Frames::terminal();
        terminal.process(b"before\x1b[?2026h after");

        clock.advance(Duration::from_millis(200));

        assert_eq!(Frames::painted_text(&terminal), "before after");
    }

    #[test]
    fn a_second_opening_keeps_the_held_screen_and_the_first_deadline() {
        let (mut terminal, clock) = Frames::terminal();
        terminal.process(b"before\x1b[?2026h first");
        clock.advance(Duration::from_millis(100));

        terminal.process(b"\x1b[?2026h second");

        assert_eq!(Frames::painted_text(&terminal), "before");
        clock.advance(Duration::from_millis(100));
        assert_eq!(Frames::painted_text(&terminal), "before first second");
    }

    #[test]
    fn is_recognised_when_its_marks_arrive_split_between_two_reads() {
        let (mut terminal, _clock) = Frames::terminal();
        terminal.process(b"before\x1b[?20");
        terminal.process(b"26h after\x1b[?2");

        assert_eq!(Frames::painted_text(&terminal), "before");

        terminal.process(b"026l");

        assert_eq!(Frames::painted_text(&terminal), "before after");
    }

    #[test]
    fn leaves_the_modes_that_read_the_keys_to_the_live_screen() {
        let (mut terminal, _clock) = Frames::terminal();

        terminal.process(b"\x1b[?2026h\x1b[?2004h\x1b[?1h\x1b[?1000h\x1b[?1006h");

        assert!(terminal.live().bracketed_paste());
        assert!(terminal.live().application_cursor());
        assert_eq!(
            terminal.live().mouse_protocol_mode(),
            vt100::MouseProtocolMode::PressRelease
        );
        assert_eq!(
            terminal.live().mouse_protocol_encoding(),
            vt100::MouseProtocolEncoding::Sgr
        );
        assert!(!terminal.painted().bracketed_paste());
    }

    #[test]
    fn is_dropped_by_a_resize_and_the_live_screen_comes_with_the_new_size() {
        let (mut terminal, _clock) = Frames::terminal();
        terminal.process(b"before\x1b[?2026h after");

        terminal.resize(10, 40);

        assert_eq!(terminal.painted().size(), (10, 40));
        assert_eq!(Frames::painted_text(&terminal), Frames::live_text(&terminal));
        assert!(Frames::painted_text(&terminal).contains("after"));
    }
}

mod without_any_frame {
    use crate::tests::infrastructure::frame_holding_terminal::Frames;

    #[test]
    fn the_painted_screen_is_the_live_one() {
        let (mut terminal, _clock) = Frames::terminal();

        terminal.process(b"plain text");

        assert_eq!(Frames::painted_text(&terminal), "plain text");
    }
}
