use ratatui::Terminal;
use ratatui::backend::TestBackend;
use ratatui::buffer::Buffer;
use ratatui::layout::Rect;

use crate::infrastructure::claude_pane::ClaudePane;
use crate::infrastructure::endless_pty_session::EndlessPtySession;

pub struct PaneScreen;

impl PaneScreen {
    pub fn painted(session: &mut EndlessPtySession, focused: bool) -> Buffer {
        let mut terminal = Terminal::new(TestBackend::new(40, 10)).unwrap();
        terminal
            .draw(|frame| ClaudePane::render(frame, Rect::new(0, 0, 40, 10), session, focused))
            .unwrap();

        terminal.backend().buffer().clone()
    }

    pub fn text_of(buffer: &Buffer) -> String {
        buffer.content().iter().map(ratatui::buffer::Cell::symbol).collect()
    }
}

mod the_claude_pane {
    use ratatui::style::Color;

    use crate::infrastructure::endless_pty_session::EndlessPtySession;
    use crate::tests::doubles::{ScriptedPtyLauncher, SteppedClock};
    use crate::tests::infrastructure::claude_pane::PaneScreen;
    use crate::tests::infrastructure::endless_pty_session::Launches;
    use crate::tests::waiting::Waiting;

    #[test]
    fn says_the_session_ended_once_claude_finishes_and_keeps_what_it_printed() {
        let (launcher, _probe) = ScriptedPtyLauncher::printing_then_ending("farewell");
        let mut session = EndlessPtySession::spawn(
            &launcher,
            &Launches::claude(),
            Launches::size(),
            SteppedClock::standing_still(),
        )
        .unwrap();
        Waiting::until(|| Launches::text_of(&session).contains("farewell").then_some(()));

        let text = PaneScreen::text_of(&PaneScreen::painted(&mut session, true));

        assert!(text.contains("claude session ended"), "{text}");
        assert!(text.contains("ctrl+q focus"), "{text}");
        assert!(text.contains("farewell"), "{text}");
    }

    #[test]
    fn does_not_say_it_while_the_session_is_alive() {
        let (launcher, _probe) = ScriptedPtyLauncher::printing("hello");
        let mut session = EndlessPtySession::spawn(
            &launcher,
            &Launches::claude(),
            Launches::size(),
            SteppedClock::standing_still(),
        )
        .unwrap();
        Waiting::until(|| Launches::text_of(&session).contains("hello").then_some(()));

        let text = PaneScreen::text_of(&PaneScreen::painted(&mut session, true));

        assert!(text.contains("hello"), "{text}");
        assert!(!text.contains("claude session ended"), "{text}");
        assert!(text.contains("ctrl+q focus"), "{text}");
    }

    #[test]
    fn highlights_the_border_only_when_it_has_the_focus() {
        let (launcher, _probe) = ScriptedPtyLauncher::printing("");
        let mut session = EndlessPtySession::spawn(
            &launcher,
            &Launches::claude(),
            Launches::size(),
            SteppedClock::standing_still(),
        )
        .unwrap();

        let focused = PaneScreen::painted(&mut session, true);
        let unfocused = PaneScreen::painted(&mut session, false);

        assert_eq!(focused[(0, 0)].fg, Color::Cyan);
        assert_ne!(unfocused[(0, 0)].fg, Color::Cyan);
    }
}
