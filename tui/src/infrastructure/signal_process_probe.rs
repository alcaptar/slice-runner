use nix::errno::Errno;
use nix::sys::signal::kill;
use nix::unistd::Pid;

use crate::domain::liveness::Liveness;
use crate::domain::process_probe::ProcessProbe;

pub struct SignalProcessProbe;

impl SignalProcessProbe {
    const LAST_RESERVED_PID: i32 = 1;
}

impl ProcessProbe for SignalProcessProbe {
    fn liveness_of(&self, pid: u32) -> Liveness {
        let Ok(raw) = i32::try_from(pid) else {
            return Liveness::Unchecked;
        };
        if raw <= Self::LAST_RESERVED_PID {
            return Liveness::Unchecked;
        }
        let Err(errno) = kill(Pid::from_raw(raw), None) else {
            return Liveness::Alive;
        };
        if errno == Errno::ESRCH {
            return Liveness::Gone;
        }
        Liveness::Unchecked
    }
}
