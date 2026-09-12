//! Reads `ControllerCommand` lines from stdin on a background thread and forwards them as
//! `EngineEvent`s to the winit/libobs thread.

use std::io::BufRead;
use winit::event_loop::EventLoopProxy;

use crate::{ControllerCommand, EngineEvent};

/// Reads `ControllerCommand` lines from stdin on a background thread and forwards the
/// ones that need the winit/libobs thread as `EngineEvent`s (libobs calls only ever happen
/// there — see `EngineEvent`'s doc). `Stop` breaks this thread's own loop too (nothing left
/// to read once the engine is exiting).
///
/// La FIN de l'entrée arrête aussi le moteur : elle signifie que le contrôleur n'est plus
/// là, et un moteur sans contrôleur ne sert plus personne — il garde seulement une caméra
/// allumée et des fichiers verrouillés.
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
                Ok(ControllerCommand::SetBackgroundRemoval {
                    device_id,
                    scene,
                    enabled,
                }) => {
                    let _ = proxy.send_event(EngineEvent::SetBackgroundRemoval {
                        device_id,
                        scene,
                        enabled,
                    });
                }
                Ok(ControllerCommand::SetMaskShape {
                    device_id,
                    scene,
                    shape,
                }) => {
                    let _ = proxy.send_event(EngineEvent::SetMaskShape {
                        device_id,
                        scene,
                        shape,
                    });
                }
                Ok(ControllerCommand::RemoveCamera { device_id, scene }) => {
                    let _ = proxy.send_event(EngineEvent::RemoveCamera { device_id, scene });
                }
                Ok(ControllerCommand::RestartCamera { device_id }) => {
                    let _ = proxy.send_event(EngineEvent::RestartCamera { device_id });
                }
                Ok(ControllerCommand::NudgeCamera {
                    device_id,
                    scene,
                    dx,
                    dy,
                }) => {
                    let _ = proxy.send_event(EngineEvent::NudgeCamera {
                        device_id,
                        scene,
                        dx,
                        dy,
                    });
                }
                Ok(ControllerCommand::ScaleCamera {
                    device_id,
                    scene,
                    grow,
                }) => {
                    let _ = proxy.send_event(EngineEvent::ScaleCamera {
                        device_id,
                        scene,
                        grow,
                    });
                }
                Ok(ControllerCommand::CreateScene { name }) => {
                    let _ = proxy.send_event(EngineEvent::CreateScene { name });
                }
                Ok(ControllerCommand::SwitchScene { name, duration_ms }) => {
                    let _ = proxy.send_event(EngineEvent::SwitchScene { name, duration_ms });
                }
                Ok(ControllerCommand::DeleteScene { name }) => {
                    let _ = proxy.send_event(EngineEvent::DeleteScene { name });
                }
                Ok(ControllerCommand::ListAudioDevices) => {
                    let _ = proxy.send_event(EngineEvent::ListAudioDevices);
                }
                Ok(ControllerCommand::AddAudioSource {
                    device_id,
                    kind,
                    name,
                }) => {
                    let _ = proxy.send_event(EngineEvent::AddAudioSource {
                        device_id,
                        kind,
                        name,
                    });
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
                Ok(ControllerCommand::SetNoiseSettings {
                    name,
                    enabled,
                    method,
                    level_db,
                }) => {
                    let _ = proxy.send_event(EngineEvent::SetNoiseSettings {
                        name,
                        enabled,
                        method,
                        level_db,
                    });
                }
                Ok(ControllerCommand::SetMonitorVolume { name, percent }) => {
                    let _ = proxy.send_event(EngineEvent::SetMonitorVolume { name, percent });
                }
                Ok(ControllerCommand::ListCaptureTargets) => {
                    let _ = proxy.send_event(EngineEvent::ListCaptureTargets);
                }
                Ok(ControllerCommand::AddCaptureSource {
                    scene,
                    kind,
                    target_id,
                    name,
                }) => {
                    let _ = proxy.send_event(EngineEvent::AddCaptureSource {
                        scene,
                        kind,
                        target_id,
                        name,
                    });
                }
                Ok(ControllerCommand::RemoveSource { scene, name }) => {
                    let _ = proxy.send_event(EngineEvent::RemoveSource { scene, name });
                }
                Ok(ControllerCommand::ReorderSource {
                    scene,
                    name,
                    direction,
                }) => {
                    let _ = proxy.send_event(EngineEvent::ReorderSource {
                        scene,
                        name,
                        direction,
                    });
                }
                Ok(ControllerCommand::SetSourceOrder {
                    scene,
                    name,
                    position,
                }) => {
                    let _ = proxy.send_event(EngineEvent::SetSourceOrder {
                        scene,
                        name,
                        position,
                    });
                }
                Ok(ControllerCommand::SetSourceTransform {
                    scene,
                    name,
                    x,
                    y,
                    scale_percent,
                }) => {
                    let _ = proxy.send_event(EngineEvent::SetSourceTransform {
                        scene,
                        name,
                        x,
                        y,
                        scale_percent,
                    });
                }
                Ok(ControllerCommand::SetSourceLocked {
                    scene,
                    name,
                    locked,
                }) => {
                    let _ = proxy.send_event(EngineEvent::SetSourceLocked {
                        scene,
                        name,
                        locked,
                    });
                }
                Ok(ControllerCommand::SetTextSettings {
                    scene,
                    name,
                    settings,
                }) => {
                    let _ = proxy.send_event(EngineEvent::SetTextSettings {
                        scene,
                        name,
                        settings,
                    });
                }
                Ok(ControllerCommand::SetTextContent { scene, name, text }) => {
                    let _ = proxy.send_event(EngineEvent::SetTextContent { scene, name, text });
                }
                Ok(ControllerCommand::RequestSceneList) => {
                    let _ = proxy.send_event(EngineEvent::RequestSceneList);
                }
                Ok(ControllerCommand::SetSourceVisible {
                    scene,
                    name,
                    visible,
                }) => {
                    let _ = proxy.send_event(EngineEvent::SetSourceVisible {
                        scene,
                        name,
                        visible,
                    });
                }
                Ok(_) => (), // ListSources : hors périmètre de ce lecteur pour l'instant
                Err(err) => eprintln!("[engine] commande stdin illisible {line:?}: {err}"),
            }
        }
        // L'ENTRÉE S'EST FERMÉE : le contrôleur n'existe plus.
        //
        // Sortir en silence laissait le moteur vivant, une caméra allumée et un
        // encodeur en marche, jusqu'au prochain redémarrage de la machine. Ce processus
        // orphelin a coûté cher à Jay : 15 fichiers verrouillés à l'installation d'une
        // mise à jour (2026-09-06), un moteur périmé conservé, et jusqu'à un plantage —
        // il écrivait encore dans un tuyau fermé.
        //
        // Le traiter ICI plutôt que côté application est ce qui le rend fiable : la fin
        // du tuyau arrive quelle que soit la façon dont l'application disparaît — fermée
        // proprement, plantée, ou tuée. Une commande d'arrêt polie, elle, suppose une
        // application encore capable de l'envoyer.
        eprintln!("[engine] entrée fermée — le contrôleur est parti, arrêt");
        let _ = proxy.send_event(EngineEvent::Exit);
    });
}
