//! Reads `ControllerCommand` lines from stdin on a background thread and forwards them as
//! `EngineEvent`s to the winit/libobs thread.

use std::io::BufRead;
use winit::event_loop::EventLoopProxy;

use crate::{ControllerCommand, EngineEvent};

/// Reads `ControllerCommand` lines from stdin on a background thread and forwards the
/// ones that need the winit/libobs thread as `EngineEvent`s (libobs calls only ever happen
/// there — see `EngineEvent`'s doc). `Stop` breaks this thread's own loop too (nothing left
/// to read once the engine is exiting).
pub(crate) fn spawn_stdin_command_reader(proxy: EventLoopProxy<EngineEvent>) {
    std::thread::spawn(move || {
        let stdin = std::io::stdin();
        for line in stdin.lock().lines().map_while(std::io::Result::ok) {
            match hikari_protocol::parse_controller_command(&line) {
                Ok(ControllerCommand::Stop) => {
                    let _ = proxy.send_event(EngineEvent::Exit);
                    break;
                }
                Ok(ControllerCommand::StartStream) => {
                    let _ = proxy.send_event(EngineEvent::StartStream);
                }
                Ok(ControllerCommand::StopStream) => {
                    let _ = proxy.send_event(EngineEvent::StopStream);
                }
                Ok(ControllerCommand::StartMultistream { targets }) => {
                    let _ = proxy.send_event(EngineEvent::StartMultistream { targets });
                }
                Ok(ControllerCommand::StopMultistream) => {
                    let _ = proxy.send_event(EngineEvent::StopMultistream);
                }
                Ok(ControllerCommand::AddCamera { device_id, scene }) => {
                    let _ = proxy.send_event(EngineEvent::AddCamera { device_id, scene });
                }
                Ok(ControllerCommand::SetBackgroundRemoval { scene, enabled }) => {
                    let _ = proxy.send_event(EngineEvent::SetBackgroundRemoval { scene, enabled });
                }
                Ok(ControllerCommand::SetCircleMask { scene, enabled }) => {
                    let _ = proxy.send_event(EngineEvent::SetCircleMask { scene, enabled });
                }
                Ok(ControllerCommand::RemoveCamera { scene }) => {
                    let _ = proxy.send_event(EngineEvent::RemoveCamera { scene });
                }
                Ok(ControllerCommand::NudgeCamera { scene, dx, dy }) => {
                    let _ = proxy.send_event(EngineEvent::NudgeCamera { scene, dx, dy });
                }
                Ok(ControllerCommand::ScaleCamera { scene, grow }) => {
                    let _ = proxy.send_event(EngineEvent::ScaleCamera { scene, grow });
                }
                Ok(ControllerCommand::CreateScene { name }) => {
                    let _ = proxy.send_event(EngineEvent::CreateScene { name });
                }
                Ok(ControllerCommand::SwitchScene { name }) => {
                    let _ = proxy.send_event(EngineEvent::SwitchScene { name });
                }
                Ok(ControllerCommand::DeleteScene { name }) => {
                    let _ = proxy.send_event(EngineEvent::DeleteScene { name });
                }
                Ok(ControllerCommand::ListAudioDevices) => {
                    let _ = proxy.send_event(EngineEvent::ListAudioDevices);
                }
                Ok(ControllerCommand::AddAudioSource { device_id, kind, name }) => {
                    let _ = proxy.send_event(EngineEvent::AddAudioSource { device_id, kind, name });
                }
                Ok(ControllerCommand::RemoveAudioSource { name }) => {
                    let _ = proxy.send_event(EngineEvent::RemoveAudioSource { name });
                }
                Ok(ControllerCommand::SetAudioVolume { name, percent }) => {
                    let _ = proxy.send_event(EngineEvent::SetAudioVolume { name, percent });
                }
                Ok(ControllerCommand::SetAudioMuted { name, muted }) => {
                    let _ = proxy.send_event(EngineEvent::SetAudioMuted { name, muted });
                }
                Ok(ControllerCommand::SetAudioMonitoring { name, monitoring }) => {
                    let _ = proxy.send_event(EngineEvent::SetAudioMonitoring { name, monitoring });
                }
                Ok(ControllerCommand::SetNoiseSettings { name, enabled, method, level_db }) => {
                    let _ = proxy
                        .send_event(EngineEvent::SetNoiseSettings { name, enabled, method, level_db });
                }
                Ok(ControllerCommand::SetMonitorVolume { name, percent }) => {
                    let _ = proxy.send_event(EngineEvent::SetMonitorVolume { name, percent });
                }
                Ok(ControllerCommand::ListCaptureTargets) => {
                    let _ = proxy.send_event(EngineEvent::ListCaptureTargets);
                }
                Ok(ControllerCommand::AddCaptureSource { scene, kind, target_id, name }) => {
                    let _ = proxy
                        .send_event(EngineEvent::AddCaptureSource { scene, kind, target_id, name });
                }
                Ok(ControllerCommand::RemoveSource { scene, name }) => {
                    let _ = proxy.send_event(EngineEvent::RemoveSource { scene, name });
                }
                Ok(ControllerCommand::ReorderSource { scene, name, direction }) => {
                    let _ = proxy.send_event(EngineEvent::ReorderSource { scene, name, direction });
                }
                Ok(ControllerCommand::SetSourceTransform { scene, name, x, y, scale_percent }) => {
                    let _ = proxy.send_event(EngineEvent::SetSourceTransform { scene, name, x, y, scale_percent });
                }
                Ok(ControllerCommand::SetSourceLocked { scene, name, locked }) => {
                    let _ = proxy.send_event(EngineEvent::SetSourceLocked { scene, name, locked });
                }
                Ok(_) => (), // ListSources : hors périmètre de ce lecteur pour l'instant
                Err(err) => eprintln!("[engine] commande stdin illisible {line:?}: {err}"),
            }
        }
    });
}
