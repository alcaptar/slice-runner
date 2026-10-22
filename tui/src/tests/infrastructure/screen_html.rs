use std::collections::HashMap;
use std::fs;
use std::path::Path;

use ratatui::buffer::{Buffer, Cell};
use ratatui::style::{Color, Modifier};

pub struct Palette {
    values: HashMap<String, String>,
}

impl Palette {
    pub fn of_the_conventions() -> Self {
        let path = Path::new(env!("CARGO_MANIFEST_DIR")).join("../docs/conventions/rust.md");

        Self::of_the_table(&fs::read_to_string(path).unwrap())
    }

    pub fn of_the_table(table: &str) -> Self {
        let values = table
            .lines()
            .filter(|line| line.starts_with("| `"))
            .filter_map(|line| {
                let cells: Vec<&str> = line.split('|').map(str::trim).collect();
                let name = cells.get(1)?.replace('`', "");
                let value = cells.get(2)?.trim_matches('`');
                value.starts_with('#').then(|| (name, value.to_string()))
            })
            .collect();

        Self { values }
    }

    pub fn background(&self) -> &str {
        self.value("Reset (fondo)")
    }

    pub fn hexadecimal(&self, color: Color) -> String {
        match color {
            Color::Reset | Color::Indexed(_) => self.value("Reset (texto)").to_string(),
            Color::Rgb(red, green, blue) => format!("#{red:02x}{green:02x}{blue:02x}"),
            Color::Black => self.value("Black").to_string(),
            Color::Red => self.value("Red").to_string(),
            Color::Green => self.value("Green").to_string(),
            Color::Yellow => self.value("Yellow").to_string(),
            Color::Blue => self.value("Blue").to_string(),
            Color::Magenta => self.value("Magenta").to_string(),
            Color::Cyan => self.value("Cyan").to_string(),
            Color::Gray => self.value("Gray").to_string(),
            Color::DarkGray => self.value("DarkGray").to_string(),
            Color::LightRed => self.value("LightRed").to_string(),
            Color::LightGreen => self.value("LightGreen").to_string(),
            Color::LightYellow => self.value("LightYellow").to_string(),
            Color::LightBlue => self.value("LightBlue").to_string(),
            Color::LightMagenta => self.value("LightMagenta").to_string(),
            Color::LightCyan => self.value("LightCyan").to_string(),
            Color::White => self.value("White").to_string(),
        }
    }

    fn value(&self, name: &str) -> &str {
        self.values.get(name).map_or("", String::as_str)
    }
}

pub struct ScreenHtml;

impl ScreenHtml {
    pub fn of(buffer: &Buffer) -> String {
        let palette = Palette::of_the_conventions();
        let mut html = format!(
            "<pre style=\"color:{};background-color:{}\">",
            palette.hexadecimal(Color::Reset),
            palette.background()
        );
        for y in 0..buffer.area.height {
            let mut style = String::new();
            let mut text = String::new();
            for x in 0..buffer.area.width {
                let cell = &buffer[(x, y)];
                let cell_style = Self::style_of(&palette, cell);
                if cell_style != style {
                    Self::close(&mut html, &style, &text);
                    text.clear();
                    style = cell_style;
                }
                text.push_str(&Self::escaped(cell.symbol()));
            }
            Self::close(&mut html, &style, &text);
            html.push('\n');
        }
        html.push_str("</pre>\n");

        html
    }

    pub fn write(directory: Option<&Path>, reference: &str, buffer: &Buffer) {
        if let Some(directory) = directory {
            fs::create_dir_all(directory).unwrap();
            fs::write(directory.join(format!("{reference}.html")), Self::of(buffer)).unwrap();
        }
    }

    fn close(html: &mut String, style: &str, text: &str) {
        if !text.is_empty() {
            html.push_str(&["<span style=\"", style, "\">", text, "</span>"].concat());
        }
    }

    fn style_of(palette: &Palette, cell: &Cell) -> String {
        let background = if matches!(cell.bg, Color::Reset | Color::Indexed(_)) {
            palette.background().to_string()
        } else {
            palette.hexadecimal(cell.bg)
        };
        let mut style = format!("color:{};background-color:{}", palette.hexadecimal(cell.fg), background);
        if cell.modifier.contains(Modifier::BOLD) {
            style.push_str(";font-weight:bold");
        }

        style
    }

    fn escaped(symbol: &str) -> String {
        symbol.replace('&', "&amp;").replace('<', "&lt;").replace('>', "&gt;")
    }
}

mod the_screen_html {
    use std::fs;
    use std::path::PathBuf;

    use ratatui::buffer::Buffer;
    use ratatui::layout::Rect;
    use ratatui::style::{Color, Modifier, Style};
    use uuid::Uuid;

    use crate::tests::infrastructure::screen_html::{Palette, ScreenHtml};

    struct Cells;

    impl Cells {
        fn row(width: u16) -> Buffer {
            Buffer::empty(Rect::new(0, 0, width, 1))
        }

        fn styled(text: &str, style: Style) -> Buffer {
            let width = u16::try_from(text.chars().count()).unwrap();
            let mut buffer = Self::row(width);
            buffer.set_string(0, 0, text, style);
            buffer
        }

        fn fresh_directory() -> PathBuf {
            std::env::temp_dir().join(format!("screen-html-{}", Uuid::new_v4()))
        }
    }

    #[test]
    fn a_colour_comes_out_with_the_value_the_table_gives_it() {
        let table = "| `Red` | `#010203` |\n| `Reset` (texto) | `#0a0b0c` |\n| `Reset` (fondo) | `#0d0e0f` |\n";
        let palette = Palette::of_the_table(table);

        assert_eq!(palette.hexadecimal(Color::Red), "#010203");
        assert_eq!(palette.hexadecimal(Color::Reset), "#0a0b0c");
        assert_eq!(palette.background(), "#0d0e0f");
    }

    #[test]
    fn the_palette_of_the_conventions_is_read_from_the_file_that_declares_it() {
        let palette = Palette::of_the_conventions();

        assert_eq!(palette.hexadecimal(Color::Cyan), "#5cc8e0");
    }

    #[test]
    fn a_cell_carries_its_character() {
        let html = ScreenHtml::of(&Cells::styled("x", Style::default()));

        assert!(html.contains(">x</span>"), "{html}");
    }

    #[test]
    fn a_cell_carries_its_text_colour() {
        let html = ScreenHtml::of(&Cells::styled("x", Style::default().fg(Color::Red)));

        assert!(html.contains("<span style=\"color:#ef6b6b;"), "{html}");
    }

    #[test]
    fn a_cell_carries_its_background() {
        let html = ScreenHtml::of(&Cells::styled("x", Style::default().bg(Color::Blue)));

        assert!(html.contains("background-color:#6b9cf2"), "{html}");
    }

    #[test]
    fn a_bold_cell_carries_the_bold_weight_and_a_plain_one_does_not() {
        let bold = ScreenHtml::of(&Cells::styled("x", Style::default().add_modifier(Modifier::BOLD)));
        let plain = ScreenHtml::of(&Cells::styled("x", Style::default()));

        assert!(bold.contains("font-weight:bold"), "{bold}");
        assert!(!plain.contains("font-weight"), "{plain}");
    }

    #[test]
    fn two_contiguous_cells_with_the_same_style_come_out_in_one_span() {
        let html = ScreenHtml::of(&Cells::styled("ab", Style::default().fg(Color::Green)));

        assert_eq!(html.matches("<span").count(), 1, "{html}");
        assert!(html.contains(">ab</span>"), "{html}");
    }

    #[test]
    fn two_contiguous_cells_with_different_style_come_out_in_two_spans() {
        let mut buffer = Cells::row(2);
        buffer.set_string(0, 0, "a", Style::default().fg(Color::Green));
        buffer.set_string(1, 0, "b", Style::default().fg(Color::Red));

        let html = ScreenHtml::of(&buffer);

        assert_eq!(html.matches("<span").count(), 2, "{html}");
    }

    #[test]
    fn every_colour_the_interface_uses_comes_out_with_the_value_of_the_palette_table() {
        let palette = [
            (Color::Cyan, "#5cc8e0"),
            (Color::DarkGray, "#6b7280"),
            (Color::Green, "#6fcf8a"),
            (Color::Red, "#ef6b6b"),
            (Color::Yellow, "#f2b53b"),
        ];

        for (color, hexadecimal) in palette {
            let html = ScreenHtml::of(&Cells::styled("x", Style::default().fg(color)));

            assert!(html.contains(&format!("color:{hexadecimal};")), "{color:?}: {html}");
        }
    }

    #[test]
    fn the_default_text_and_background_come_out_with_their_own_values() {
        let html = ScreenHtml::of(&Cells::styled("x", Style::default()));

        assert!(
            html.contains("<span style=\"color:#d8dde6;background-color:#0f1216"),
            "{html}"
        );
    }

    #[test]
    fn markup_characters_are_escaped() {
        let html = ScreenHtml::of(&Cells::styled("<&>", Style::default()));

        assert!(html.contains("&lt;&amp;&gt;"), "{html}");
    }

    #[test]
    fn with_a_directory_it_writes_the_html_named_after_its_reference() {
        let directory = Cells::fresh_directory();
        let buffer = Cells::styled("x", Style::default());

        ScreenHtml::write(Some(&directory), "bandeja", &buffer);

        let written = fs::read_to_string(directory.join("bandeja.html")).unwrap();
        fs::remove_dir_all(&directory).unwrap();
        assert_eq!(written, ScreenHtml::of(&buffer));
    }

    #[test]
    fn without_a_directory_it_writes_nothing() {
        ScreenHtml::write(None, "bandeja", &Cells::styled("x", Style::default()));

        assert!(!PathBuf::from("bandeja.html").exists());
    }
}
