use std::collections::VecDeque;
use std::io::{self, Cursor, Read, Write};
use std::path::{Path, PathBuf};
use std::sync::atomic::{AtomicBool, Ordering};
use std::sync::mpsc::{self, Receiver, Sender};
use std::sync::{Arc, Mutex};
use std::time::{Duration, Instant};

use crate::domain::clock::Clock;
use crate::domain::comparison_opener::ComparisonOpener;
use crate::domain::errors::{ComparisonNotOpened, FollowLineRejected, IssuesUnread};
use crate::domain::follow_entry::FollowEntry;
use crate::domain::follow_source::FollowSource;
use crate::domain::issue_source::IssueSource;
use crate::domain::issue_text::IssueText;
use crate::domain::liveness::Liveness;
use crate::domain::open_issue::OpenIssue;
use crate::domain::pane_size::PaneSize;
use crate::domain::process_probe::ProcessProbe;
use crate::domain::program_update::ProgramUpdate;
use crate::domain::session_transcripts::SessionTranscripts;
use crate::domain::update_availability::UpdateAvailability;
use crate::domain::update_check::UpdateCheck;
use crate::domain::update_progress::UpdateProgress;
use crate::domain::workspace_id::WorkspaceId;
use crate::domain::workspace_ids::WorkspaceIds;
use crate::infrastructure::child_launcher::{ChildExit, ChildLauncher, Launch, RunningChild, Stream};
use crate::infrastructure::pty_launcher::{LaunchedPty, PtyLauncher, PtyResizer};
use crate::tests::mothers::workspace_mother::WorkspaceMother;

pub type Delivery = Result<FollowEntry, FollowLineRejected>;

pub struct ScriptedFollowSource {
    batches: VecDeque<Vec<Delivery>>,
}

impl ScriptedFollowSource {
    pub fn delivering(batches: Vec<Vec<Delivery>>) -> Self {
        Self {
            batches: batches.into(),
        }
    }
}

impl FollowSource for ScriptedFollowSource {
    fn pending(&mut self) -> Vec<Delivery> {
        self.batches.pop_front().unwrap_or_default()
    }
}

pub struct FixedWorkspaceIds {
    id: WorkspaceId,
}

impl FixedWorkspaceIds {
    pub fn always(text: &str) -> Self {
        Self {
            id: WorkspaceId::parse(text).unwrap(),
        }
    }
}

impl WorkspaceIds for FixedWorkspaceIds {
    fn next(&mut self) -> WorkspaceId {
        self.id.clone()
    }
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub enum Call {
    RepoView,
    IssueList { repo: String, limit: usize },
    IssueView { repo: String, number: u64 },
}

pub type Calls = Arc<Mutex<Vec<Call>>>;

pub struct ScriptedIssueSource {
    repos: VecDeque<Result<String, IssuesUnread>>,
    lists: VecDeque<Result<Vec<OpenIssue>, IssuesUnread>>,
    bodies: VecDeque<Result<IssueText, IssuesUnread>>,
    calls: Calls,
}

impl ScriptedIssueSource {
    pub fn answering(
        repos: Vec<Result<String, IssuesUnread>>,
        lists: Vec<Result<Vec<OpenIssue>, IssuesUnread>>,
    ) -> (Self, Calls) {
        let calls = Calls::default();

        (
            Self {
                repos: repos.into(),
                lists: lists.into(),
                bodies: VecDeque::new(),
                calls: Arc::clone(&calls),
            },
            calls,
        )
    }

    pub fn with_bodies(mut self, bodies: Vec<Result<String, IssuesUnread>>) -> Self {
        self.bodies = bodies
            .into_iter()
            .map(|body| body.map(|body| IssueText::new(&body, WorkspaceMother::PARENT_TITLE)))
            .collect();

        self
    }

    fn unscripted(what: &str) -> IssuesUnread {
        IssuesUnread::CommandFailed {
            reason: format!("nobody scripted an answer for {what}"),
        }
    }
}

impl IssueSource for ScriptedIssueSource {
    fn repo_of_directory(&mut self) -> Result<String, IssuesUnread> {
        self.calls.lock().unwrap().push(Call::RepoView);

        self.repos
            .pop_front()
            .unwrap_or_else(|| Err(Self::unscripted("repo view")))
    }

    fn latest_open(&mut self, repo: &str, limit: usize) -> Result<Vec<OpenIssue>, IssuesUnread> {
        self.calls.lock().unwrap().push(Call::IssueList {
            repo: repo.to_string(),
            limit,
        });

        self.lists
            .pop_front()
            .unwrap_or_else(|| Err(Self::unscripted("issue list")))
    }

    fn body_of(&mut self, repo: &str, number: u64) -> Result<IssueText, IssuesUnread> {
        self.calls.lock().unwrap().push(Call::IssueView {
            repo: repo.to_string(),
            number,
        });

        self.bodies
            .pop_front()
            .unwrap_or_else(|| Err(Self::unscripted("issue view")))
    }
}

pub struct ScriptedTranscripts {
    existing: bool,
}

impl ScriptedTranscripts {
    pub fn present() -> Self {
        Self { existing: true }
    }

    pub fn absent() -> Self {
        Self { existing: false }
    }
}

impl SessionTranscripts for ScriptedTranscripts {
    fn exists(&self, _directory: &Path, _id: &WorkspaceId) -> bool {
        self.existing
    }
}

#[derive(Clone)]
pub struct SteppedClock {
    start: Instant,
    elapsed: Arc<Mutex<Duration>>,
}

impl SteppedClock {
    pub fn standing_still() -> Self {
        Self {
            start: Instant::now(),
            elapsed: Arc::default(),
        }
    }

    pub fn advance(&self, by: Duration) {
        *self.elapsed.lock().unwrap() += by;
    }
}

impl Clock for SteppedClock {
    fn now(&self) -> Instant {
        self.start + *self.elapsed.lock().unwrap()
    }
}

pub struct GatedIssueSource {
    gate: Receiver<()>,
}

impl GatedIssueSource {
    pub fn closed() -> (Self, Sender<()>) {
        let (release, gate) = mpsc::channel();

        (Self { gate }, release)
    }
}

impl IssueSource for GatedIssueSource {
    fn repo_of_directory(&mut self) -> Result<String, IssuesUnread> {
        Ok(WorkspaceMother::REPO.to_string())
    }

    fn latest_open(&mut self, _repo: &str, _limit: usize) -> Result<Vec<OpenIssue>, IssuesUnread> {
        self.gate.recv().ok();

        Ok(vec![WorkspaceMother::parent_of_this_workspace(9)])
    }

    fn body_of(&mut self, _repo: &str, _number: u64) -> Result<IssueText, IssuesUnread> {
        Err(IssuesUnread::CommandFailed {
            reason: "nobody scripted an answer for issue view".to_string(),
        })
    }
}

pub struct FixedProbe {
    alive: Vec<u32>,
    everyone_alive: bool,
}

impl FixedProbe {
    pub fn everyone_alive() -> Self {
        Self {
            alive: Vec::new(),
            everyone_alive: true,
        }
    }

    pub fn alive_only(alive: &[u32]) -> Self {
        Self {
            alive: alive.to_vec(),
            everyone_alive: false,
        }
    }
}

impl ProcessProbe for FixedProbe {
    fn liveness_of(&self, pid: u32) -> Liveness {
        if self.everyone_alive || self.alive.contains(&pid) {
            return Liveness::Alive;
        }

        Liveness::Gone
    }
}

pub struct UnaskedProbe;

impl ProcessProbe for UnaskedProbe {
    fn liveness_of(&self, pid: u32) -> Liveness {
        panic!("the probe was asked about {pid}")
    }
}

pub type OpenerCalls = Arc<Mutex<Vec<String>>>;

pub struct RecordingOpener {
    outcome: Result<(), ComparisonNotOpened>,
    calls: OpenerCalls,
}

impl RecordingOpener {
    pub fn succeeding() -> (Self, OpenerCalls) {
        Self::answering(Ok(()))
    }

    pub fn failing(failure: ComparisonNotOpened) -> (Self, OpenerCalls) {
        Self::answering(Err(failure))
    }

    fn answering(outcome: Result<(), ComparisonNotOpened>) -> (Self, OpenerCalls) {
        let calls = OpenerCalls::default();

        (
            Self {
                outcome,
                calls: Arc::clone(&calls),
            },
            calls,
        )
    }
}

impl ComparisonOpener for RecordingOpener {
    fn open(&mut self, path: &str) -> Result<(), ComparisonNotOpened> {
        self.calls.lock().unwrap().push(path.to_string());

        self.outcome.clone()
    }
}

pub struct GatedUpdateCheck {
    gate: Receiver<()>,
    answer: UpdateAvailability,
}

impl GatedUpdateCheck {
    pub fn closed(answer: UpdateAvailability) -> (Self, Sender<()>) {
        let (release, gate) = mpsc::channel();

        (Self { gate, answer }, release)
    }
}

impl UpdateCheck for GatedUpdateCheck {
    fn availability(&mut self) -> UpdateAvailability {
        self.gate.recv().ok();

        self.answer.clone()
    }
}

pub struct FixedUpdateCheck {
    answer: UpdateAvailability,
}

impl FixedUpdateCheck {
    pub fn answering(answer: UpdateAvailability) -> Self {
        Self { answer }
    }
}

impl UpdateCheck for FixedUpdateCheck {
    fn availability(&mut self) -> UpdateAvailability {
        self.answer.clone()
    }
}

pub type Launches = Arc<Mutex<Vec<String>>>;

pub struct ScriptedProgramUpdate {
    progress: UpdateProgress,
    launches: Launches,
}

impl ScriptedProgramUpdate {
    pub fn reporting(progress: UpdateProgress) -> (Self, Launches) {
        let launches = Launches::default();

        (
            Self {
                progress,
                launches: Arc::clone(&launches),
            },
            launches,
        )
    }
}

impl ProgramUpdate for ScriptedProgramUpdate {
    fn start(&mut self, version: &str) {
        self.launches.lock().unwrap().push(version.to_string());
    }

    fn progress(&mut self) -> UpdateProgress {
        self.progress.clone()
    }
}

pub struct AdvancingClock {
    start: Instant,
    step: Duration,
    elapsed: Mutex<Duration>,
}

impl AdvancingClock {
    pub fn stepping(step: Duration) -> Self {
        Self {
            start: Instant::now(),
            step,
            elapsed: Mutex::default(),
        }
    }
}

impl Clock for AdvancingClock {
    fn now(&self) -> Instant {
        let mut elapsed = self.elapsed.lock().unwrap();
        let now = self.start + *elapsed;
        *elapsed += self.step;

        now
    }
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub enum ChildCall {
    Launched { argv: Vec<String>, launch: Launch },
    Killed,
    Waited,
    Exited,
}

pub type ChildCalls = Arc<Mutex<Vec<ChildCall>>>;

#[derive(Clone)]
pub struct ScriptedChild {
    exit: Option<ChildExit>,
    stdout: String,
    stderr: String,
    gate: Option<Arc<AtomicBool>>,
    calls: ChildCalls,
}

impl ScriptedChild {
    fn boxed_stream(text: &str) -> Box<dyn Read + Send> {
        Box::new(Cursor::new(text.as_bytes().to_vec()))
    }
}

impl RunningChild for ScriptedChild {
    fn try_wait(&mut self) -> io::Result<Option<ChildExit>> {
        let Some(gate) = &self.gate else {
            return Ok(self.exit);
        };
        if !gate.load(Ordering::SeqCst) {
            return Ok(None);
        }
        self.calls.lock().unwrap().push(ChildCall::Exited);

        Ok(self.exit)
    }

    fn kill(&mut self) -> io::Result<()> {
        self.calls.lock().unwrap().push(ChildCall::Killed);

        Ok(())
    }

    fn wait(&mut self) -> io::Result<ChildExit> {
        self.calls.lock().unwrap().push(ChildCall::Waited);

        Ok(self.exit.unwrap_or(ChildExit::Signal))
    }

    fn take_stdout(&mut self) -> Option<Box<dyn Read + Send>> {
        Some(Self::boxed_stream(&self.stdout))
    }

    fn take_stderr(&mut self) -> Option<Box<dyn Read + Send>> {
        Some(Self::boxed_stream(&self.stderr))
    }
}

pub struct ScriptedChildLauncher {
    child: Result<ScriptedChild, String>,
    calls: ChildCalls,
}

pub struct ChildGate {
    open: Arc<AtomicBool>,
}

impl ChildGate {
    pub fn open(&self) {
        self.open.store(true, Ordering::SeqCst);
    }
}

impl ScriptedChildLauncher {
    pub fn answering(exit: ChildExit, stdout: &str, stderr: &str) -> (Self, ChildCalls) {
        Self::launching(Some(exit), stdout, stderr, None)
    }

    pub fn never_ending() -> (Self, ChildCalls) {
        Self::launching(None, "", "", None)
    }

    pub fn streaming(stdout: &str) -> (Self, ChildCalls) {
        Self::launching(None, stdout, "", None)
    }

    pub fn finishing_once_released(exit: ChildExit) -> (Self, ChildCalls, ChildGate) {
        let open = Arc::new(AtomicBool::new(false));
        let (launcher, calls) = Self::launching(Some(exit), "", "", Some(Arc::clone(&open)));

        (launcher, calls, ChildGate { open })
    }

    pub fn unlaunchable(reason: &str) -> (Self, ChildCalls) {
        let calls = ChildCalls::default();

        (
            Self {
                child: Err(reason.to_string()),
                calls: Arc::clone(&calls),
            },
            calls,
        )
    }

    fn launching(
        exit: Option<ChildExit>,
        stdout: &str,
        stderr: &str,
        gate: Option<Arc<AtomicBool>>,
    ) -> (Self, ChildCalls) {
        let calls = ChildCalls::default();
        let child = ScriptedChild {
            exit,
            stdout: stdout.to_string(),
            stderr: stderr.to_string(),
            gate,
            calls: Arc::clone(&calls),
        };

        (
            Self {
                child: Ok(child),
                calls: Arc::clone(&calls),
            },
            calls,
        )
    }
}

impl ChildLauncher for ScriptedChildLauncher {
    fn launched(&self, argv: &[String], options: &Launch) -> Result<Box<dyn RunningChild>, io::Error> {
        self.calls.lock().unwrap().push(ChildCall::Launched {
            argv: argv.to_vec(),
            launch: options.clone(),
        });

        match &self.child {
            Ok(child) => {
                if let Stream::File(path) = options.stderr() {
                    std::fs::write(path, &child.stderr)?;
                }

                Ok(Box::new(child.clone()))
            }
            Err(reason) => Err(io::Error::other(reason.clone())),
        }
    }
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub enum PtyCall {
    Launched {
        argv: Vec<String>,
        directory: PathBuf,
        environment: Vec<(String, String)>,
        size: PaneSize,
    },
    Resized(PaneSize),
}

pub type PtyCalls = Arc<Mutex<Vec<PtyCall>>>;
pub type Written = Arc<Mutex<Vec<u8>>>;

pub struct PtyProbe {
    calls: PtyCalls,
    written: Written,
    child_calls: ChildCalls,
    gate: ChildGate,
}

impl PtyProbe {
    pub fn calls(&self) -> Vec<PtyCall> {
        self.calls.lock().unwrap().clone()
    }

    pub fn written(&self) -> Vec<u8> {
        self.written.lock().unwrap().clone()
    }

    pub fn child_calls(&self) -> Vec<ChildCall> {
        self.child_calls.lock().unwrap().clone()
    }

    pub fn end_the_child(&self) {
        self.gate.open();
    }
}

struct RecordingWriter {
    written: Written,
}

impl Write for RecordingWriter {
    fn write(&mut self, bytes: &[u8]) -> io::Result<usize> {
        self.written.lock().unwrap().extend_from_slice(bytes);

        Ok(bytes.len())
    }

    fn flush(&mut self) -> io::Result<()> {
        Ok(())
    }
}

struct RecordingResizer {
    calls: PtyCalls,
}

impl PtyResizer for RecordingResizer {
    fn resize(&mut self, size: PaneSize) -> io::Result<()> {
        self.calls.lock().unwrap().push(PtyCall::Resized(size));

        Ok(())
    }
}

pub struct ScriptedPtyLauncher {
    output: Vec<u8>,
    failure: Option<String>,
    exit: Option<ChildExit>,
    gate: Arc<AtomicBool>,
    probe_calls: PtyCalls,
    probe_written: Written,
    probe_child_calls: ChildCalls,
}

impl ScriptedPtyLauncher {
    pub fn printing(output: &str) -> (Self, PtyProbe) {
        Self::scripted(output, None, Some(ChildExit::Code(0)), false)
    }

    pub fn printing_then_ending(output: &str) -> (Self, PtyProbe) {
        Self::scripted(output, None, Some(ChildExit::Code(0)), true)
    }

    pub fn unlaunchable(reason: &str) -> (Self, PtyProbe) {
        Self::scripted("", Some(reason.to_string()), None, false)
    }

    fn scripted(output: &str, failure: Option<String>, exit: Option<ChildExit>, ended: bool) -> (Self, PtyProbe) {
        let gate = Arc::new(AtomicBool::new(ended));
        let launcher = Self {
            output: output.as_bytes().to_vec(),
            failure,
            exit,
            gate: Arc::clone(&gate),
            probe_calls: PtyCalls::default(),
            probe_written: Written::default(),
            probe_child_calls: ChildCalls::default(),
        };
        let probe = PtyProbe {
            calls: Arc::clone(&launcher.probe_calls),
            written: Arc::clone(&launcher.probe_written),
            child_calls: Arc::clone(&launcher.probe_child_calls),
            gate: ChildGate { open: gate },
        };

        (launcher, probe)
    }
}

impl PtyLauncher for ScriptedPtyLauncher {
    fn launched(
        &self,
        argv: &[String],
        directory: &Path,
        environment: &[(String, String)],
        size: PaneSize,
    ) -> io::Result<LaunchedPty> {
        self.probe_calls.lock().unwrap().push(PtyCall::Launched {
            argv: argv.to_vec(),
            directory: directory.to_path_buf(),
            environment: environment.to_vec(),
            size,
        });
        if let Some(reason) = &self.failure {
            return Err(io::Error::other(reason.clone()));
        }
        let child = ScriptedChild {
            exit: self.exit,
            stdout: String::new(),
            stderr: String::new(),
            gate: Some(Arc::clone(&self.gate)),
            calls: Arc::clone(&self.probe_child_calls),
        };

        Ok(LaunchedPty::new(
            Box::new(Cursor::new(self.output.clone())),
            Box::new(RecordingWriter {
                written: Arc::clone(&self.probe_written),
            }),
            Box::new(RecordingResizer {
                calls: Arc::clone(&self.probe_calls),
            }),
            Box::new(child),
        ))
    }
}
