use std::io;
use std::path::PathBuf;
use std::process::ExitCode;
use std::sync::Arc;
use std::time::Duration;

use crossterm::event::{self, Event, KeyEvent, MouseEvent};
use ratatui::Frame;
use ratatui::layout::{Constraint, Layout, Rect};

use crate::application::actions::open_comparison::OpenComparison;
use crate::application::actions::reopen_workspace::{ReopenWorkspace, ReopenWorkspaceParams};
use crate::application::actions::start_claude_session::{StartClaudeSession, StartClaudeSessionParams};
use crate::application::actions::update_in_background::UpdateInBackground;
use crate::application::queries::bind_workspace::{BindWorkspace, WorkspaceState};
use crate::application::queries::read_slice_detail::{ReadSliceDetail, SliceDetail};
use crate::application::queries::watch_slices::WatchSlices;
use crate::domain::auto_update::AutoUpdate;
use crate::domain::binding_cadence::BindingCadence;
use crate::domain::pane_size::PaneSize;
use crate::domain::session_launch::SessionLaunch;
use crate::domain::slice_board::SliceBoard;
use crate::domain::slice_key::SliceKey;
use crate::domain::update_availability::UpdateAvailability;
use crate::domain::wall_clock::WallClock;
use crate::infrastructure::board_view::BoardView;
use crate::infrastructure::bounded_gh_process::BoundedGhProcess;
use crate::infrastructure::bounded_open_process::BoundedOpenProcess;
use crate::infrastructure::bounded_update_check_process::BoundedUpdateCheckProcess;
use crate::infrastructure::claude_config_root::ClaudeConfigRoot;
use crate::infrastructure::claude_pane::ClaudePane;
use crate::infrastructure::config_dir_session_transcripts::ConfigDirSessionTranscripts;
use crate::infrastructure::detached_program_update::DetachedProgramUpdate;
use crate::infrastructure::endless_follow_process::EndlessFollowProcess;
use crate::infrastructure::endless_pty_session::EndlessPtySession;
use crate::infrastructure::key_bytes::KeyBytes;
use crate::infrastructure::key_routing::{Focus, KeyRouting, Order, Routed};
use crate::infrastructure::mouse_bytes::MouseBytes;
use crate::infrastructure::mouse_routing::{MouseEffect, MouseRouting};
use crate::infrastructure::os_child_launcher::OsChildLauncher;
use crate::infrastructure::os_group_child_launcher::OsGroupChildLauncher;
use crate::infrastructure::os_pty_launcher::OsPtyLauncher;
use crate::infrastructure::random_workspace_ids::RandomWorkspaceIds;
use crate::infrastructure::signal_process_probe::SignalProcessProbe;
use crate::infrastructure::slice_areas::SliceAreas;
use crate::infrastructure::split_screen::SplitScreen;
use crate::infrastructure::system_clock::SystemClock;
use crate::infrastructure::terminal_session::TerminalSession;
use crate::infrastructure::threaded_update_check::ThreadedUpdateCheck;
use crate::infrastructure::threaded_workspace_binding::ThreadedWorkspaceBinding;
use crate::infrastructure::update_notice_view::UpdateNoticeView;
use crate::infrastructure::workspace_header::WorkspaceHeader;

enum Input {
    Key(KeyEvent),
    Paste(String),
    Mouse(MouseEvent),
    Resized(PaneSize),
    Nothing,
}

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum Invocation {
    Fresh,
    Reopen(u64),
    Version,
}

pub struct Cli;

impl Cli {
    pub const VERSION: &'static str = env!("CARGO_PKG_VERSION");
    const VERSION_FLAG: &'static str = "--version";
    const PROGRAM: &'static str = "slice-runner";
    const FOLLOW_ARGV: [&'static str; 3] = [Self::PROGRAM, "follow", "--json"];
    const TICK: Duration = Duration::from_millis(100);
    const GH_PROGRAM: &'static str = "gh";
    const GH_BUDGET: Duration = Duration::from_secs(10);
    const UPDATE_CHECK_BUDGET: Duration = Duration::from_secs(20);
    pub const UPDATE_BUDGET: Duration = Duration::from_mins(5);
    const DISABLE_AUTOUPDATE_VARIABLE: &'static str = "SLICE_RUNNER_DISABLE_AUTOUPDATE";
    const DISABLE_AUTOUPDATE_VALUE: &'static str = "1";
    const OPEN_PROGRAM: &'static str = "open";
    const OPEN_BUDGET: Duration = Duration::from_secs(10);
    const BINDING_INTERVAL: Duration = Duration::from_secs(5);
    const BINDING_LIMIT: usize = 20;

    pub fn main() -> ExitCode {
        let arguments: Vec<String> = std::env::args().skip(1).collect();
        let outcome = Self::invocation_of(&arguments).and_then(Self::run);
        match outcome {
            Ok(()) => ExitCode::SUCCESS,
            Err(error) => {
                eprintln!("slice-runner-tui: {error}");
                ExitCode::FAILURE
            }
        }
    }

    pub fn invocation_of(arguments: &[String]) -> Result<Invocation, String> {
        match arguments {
            [] => Ok(Invocation::Fresh),
            [flag] if flag == Self::VERSION_FLAG => Ok(Invocation::Version),
            [number] => number
                .parse::<u64>()
                .map(Invocation::Reopen)
                .map_err(|_| format!("usage: slice-runner-tui [<parent number>], got `{number}`")),
            _ => Err("usage: slice-runner-tui [<parent number>]".to_string()),
        }
    }

    fn gh() -> BoundedGhProcess {
        BoundedGhProcess::new(
            vec![Self::GH_PROGRAM.to_string()],
            Arc::new(OsChildLauncher),
            SystemClock,
            Self::GH_BUDGET,
        )
    }

    fn follow_source() -> Result<EndlessFollowProcess, String> {
        EndlessFollowProcess::spawn(&OsChildLauncher, &Self::FOLLOW_ARGV).map_err(|rejected| rejected.to_string())
    }

    fn claude_session(launch: &SessionLaunch, size: PaneSize) -> Result<EndlessPtySession, String> {
        EndlessPtySession::spawn(&OsPtyLauncher, launch, size, SystemClock).map_err(|rejected| rejected.to_string())
    }

    fn reopened(parent: u64, directory: PathBuf) -> Result<(SessionLaunch, WorkspaceState), String> {
        let config =
            ClaudeConfigRoot::resolved().ok_or_else(|| "neither CLAUDE_CONFIG_DIR nor HOME is set".to_string())?;
        let reopened = ReopenWorkspace::new(Self::gh(), ConfigDirSessionTranscripts::new(config))
            .execute(ReopenWorkspaceParams::new(directory, parent))
            .map_err(|rejected| rejected.to_string())?;

        Ok((reopened.launch().clone(), reopened.into_state()))
    }

    fn run(invocation: Invocation) -> Result<(), String> {
        if invocation == Invocation::Version {
            println!("{}", Self::VERSION);

            return Ok(());
        }

        let directory = std::env::current_dir().map_err(|error| error.to_string())?;
        let (launch, state) = match invocation {
            Invocation::Fresh => {
                let launch = StartClaudeSession::new(RandomWorkspaceIds)
                    .execute(StartClaudeSessionParams::in_directory(directory));

                (launch, None)
            }
            Invocation::Reopen(parent) => {
                let (launch, state) = Self::reopened(parent, directory)?;

                (launch, Some(state))
            }
            Invocation::Version => return Ok(()),
        };
        let mut watch = WatchSlices::new(Self::follow_source()?, SignalProcessProbe);
        let mut session = TerminalSession::open().map_err(|error| error.to_string())?;
        let window = session.terminal().size().map_err(|error| error.to_string())?;
        let mut claude = Self::claude_session(&launch, SplitScreen::pane_size(Rect::from(window)))?;
        let gh = Self::gh();
        let cadence = BindingCadence::new(Self::BINDING_INTERVAL, Self::BINDING_LIMIT);
        let bind = match state {
            Some(state) => BindWorkspace::from_state(gh, SystemClock, cadence, state),
            None => BindWorkspace::new(gh, SystemClock, cadence, launch.workspace().clone()),
        };
        let mut binding = ThreadedWorkspaceBinding::start(bind, Self::BINDING_INTERVAL);
        let mut open_comparison = Self::open_comparison();
        let mut update_notice = Self::update_notice();
        let mut focus = Focus::Claude;
        let mut mouse = MouseBytes::default();
        let mut board = SliceBoard::empty();
        let mut selected: Option<SliceKey> = None;
        let mut detail: Option<SliceDetail> = None;
        let mut slice_areas = SliceAreas::empty();
        loop {
            let workspace = binding.latest();
            let watched = watch.execute(board);
            let shown = watched.shown_for(&workspace);
            let update = update_notice.execute();
            session
                .terminal()
                .draw(|frame| {
                    let (claude_area, board_area) = SplitScreen::areas(frame.area());
                    ClaudePane::render(frame, claude_area, &mut claude, focus == Focus::Claude);
                    let slices_area = Self::render_chrome(frame, board_area, &workspace, &update);
                    slice_areas = BoardView::render(
                        frame,
                        slices_area,
                        &shown,
                        selected.as_ref(),
                        detail.as_ref(),
                        SystemClock.epoch_millis(),
                        focus == Focus::Board,
                    );
                })
                .map_err(|error| error.to_string())?;
            match Self::next_input().map_err(|error| error.to_string())? {
                Input::Resized(size) => claude.resize(size),
                Input::Mouse(event) => {
                    let opened =
                        Self::apply_mouse(&mut session, &mut claude, &mut mouse, event, &mut focus, &slice_areas)?;
                    Self::opened(opened, &mut selected, &mut detail);
                }
                Input::Paste(text) => {
                    if focus == Focus::Claude {
                        claude.write(&claude.with_screen(|screen| KeyBytes::of_paste(&text, screen)));
                    }
                }
                Input::Key(key) => match claude.with_screen(|screen| KeyRouting::route(focus, key, screen)) {
                    Routed::ToClaude(bytes) => claude.write(&bytes),
                    Routed::ToggleFocus => focus = focus.toggled(),
                    Routed::Board(Order::Quit) => return Ok(()),
                    Routed::Board(Order::Previous) => {
                        let target = shown.board().before(selected.as_ref());
                        Self::moved(&mut selected, target, &mut detail);
                    }
                    Routed::Board(Order::Next) => {
                        let target = shown.board().after(selected.as_ref());
                        Self::moved(&mut selected, target, &mut detail);
                    }
                    Routed::Board(Order::Open) => {
                        if let Some(key) = selected.clone() {
                            detail = Some(ReadSliceDetail::execute(key));
                        }
                    }
                    Routed::Board(Order::OpenComparison) => {
                        let opening = open_comparison.execute(shown.board(), detail.as_ref());
                        detail = detail.map(|detail| detail.after(opening));
                    }
                    Routed::Board(Order::Close) => detail = None,
                    Routed::Ignored | Routed::Board(Order::Nothing) => {}
                },
                Input::Nothing => {}
            }
            board = watched.into_board();
        }
    }

    fn render_chrome(frame: &mut Frame, area: Rect, workspace: &WorkspaceState, update: &UpdateAvailability) -> Rect {
        let [header_area, slices_area, notice_area] = Layout::vertical([
            Constraint::Length(WorkspaceHeader::HEIGHT),
            Constraint::Min(0),
            Constraint::Length(UpdateNoticeView::height_of(update)),
        ])
        .areas(area);
        WorkspaceHeader::render(frame, header_area, workspace);
        UpdateNoticeView::render(frame, notice_area, update);

        slices_area
    }

    fn apply_mouse(
        session: &mut TerminalSession,
        claude: &mut EndlessPtySession,
        mouse: &mut MouseBytes,
        event: MouseEvent,
        focus: &mut Focus,
        slices: &SliceAreas,
    ) -> Result<Option<SliceKey>, String> {
        let window = session.terminal().size().map_err(|error| error.to_string())?;
        let action = claude.with_screen(|screen| MouseRouting::route(event, Rect::from(window), mouse, screen, slices));
        if let Some(target) = action.focus() {
            *focus = target;
        }
        match action.effect() {
            MouseEffect::ToClaude(bytes) => {
                claude.write(bytes);
                Ok(None)
            }
            MouseEffect::Open(key) => Ok(Some(key.clone())),
            MouseEffect::Nothing => Ok(None),
        }
    }

    pub fn auto_update_of(disable_variable: Option<&str>) -> AutoUpdate {
        match disable_variable {
            Some(Self::DISABLE_AUTOUPDATE_VALUE) => AutoUpdate::Disabled,
            Some(_) | None => AutoUpdate::Enabled,
        }
    }

    fn update_notice() -> UpdateInBackground<ThreadedUpdateCheck, DetachedProgramUpdate> {
        let check = ThreadedUpdateCheck::start(BoundedUpdateCheckProcess::new(
            vec![Self::PROGRAM.to_string()],
            Arc::new(OsChildLauncher),
            SystemClock,
            Self::UPDATE_CHECK_BUDGET,
        ));
        let update = DetachedProgramUpdate::new(
            vec![Self::PROGRAM.to_string()],
            Arc::new(OsGroupChildLauncher),
            SystemClock,
            Self::UPDATE_BUDGET,
            std::env::temp_dir(),
        );
        let disable_variable = std::env::var(Self::DISABLE_AUTOUPDATE_VARIABLE).ok();

        UpdateInBackground::new(check, update, Self::auto_update_of(disable_variable.as_deref()))
    }

    fn open_comparison() -> OpenComparison<BoundedOpenProcess> {
        OpenComparison::new(BoundedOpenProcess::new(
            vec![Self::OPEN_PROGRAM.to_string()],
            Arc::new(OsChildLauncher),
            SystemClock,
            Self::OPEN_BUDGET,
        ))
    }

    fn opened(key: Option<SliceKey>, selected: &mut Option<SliceKey>, detail: &mut Option<SliceDetail>) {
        if let Some(key) = key {
            *detail = Some(ReadSliceDetail::execute(key.clone()));
            *selected = Some(key);
        }
    }

    fn moved(selected: &mut Option<SliceKey>, target: Option<SliceKey>, detail: &mut Option<SliceDetail>) {
        if target.is_some() && target != *selected {
            *detail = None;
            *selected = target;
        }
    }

    fn next_input() -> io::Result<Input> {
        if !event::poll(Self::TICK)? {
            return Ok(Input::Nothing);
        }

        Ok(match event::read()? {
            Event::Key(key) => Input::Key(key),
            Event::Paste(text) => Input::Paste(text),
            Event::Resize(columns, rows) => Input::Resized(SplitScreen::pane_size(Rect::new(0, 0, columns, rows))),
            Event::Mouse(event) => Input::Mouse(event),
            Event::FocusGained | Event::FocusLost => Input::Nothing,
        })
    }
}
