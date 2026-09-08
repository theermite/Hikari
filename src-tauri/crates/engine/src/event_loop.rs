//! The winit `ApplicationHandler` for `App` — dispatches every `EngineEvent` (from stdin)
//! to its `handle_*` method, and every native window event (resize, cursor, click) to the
//! drag machinery.

use std::time::Instant;
use libobs_wrapper::display::WindowPositionTrait;
use winit::application::ApplicationHandler;
use winit::event::{ElementState, MouseButton, WindowEvent};
use winit::event_loop::{ActiveEventLoop, ControlFlow};
use winit::window::WindowId;

use crate::stream::{FRAME_STATS_INTERVAL, report_frame_stats};
use crate::multistream::report_platform_frame_stats;
use crate::{App, AUDIO_LEVEL_INTERVAL, CAMERA_SLIDE_TICK, EngineEvent, emit, fit_size};
use hikari_protocol::EngineMessage;

impl ApplicationHandler<EngineEvent> for App {
    fn resumed(&mut self, event_loop: &ActiveEventLoop) {
        // `try_init` never runs twice (winit calls `resumed` once per real app lifecycle
        // on Windows) but `try_init` returning early is still preferable to a second panic
        // if that assumption ever breaks — `env_logger::try_init` tolerates a repeat call.
        let _ = env_logger::try_init();
        if let Err(err) = self.try_init(event_loop) {
            emit(&EngineMessage::Error { message: err.to_string() });
            event_loop.exit();
        }
    }

    fn user_event(&mut self, event_loop: &ActiveEventLoop, event: EngineEvent) {
        // Ce que les scènes contiennent AVANT la commande.
        //
        // POURQUOI ce filet plutôt qu'un appel de plus dans chaque commande (2026-09-06) :
        // deux commandes ont oublié d'annoncer la nouvelle composition le même jour —
        // poser une caméra et en retirer une. Le symptôme est muet des deux côtés : le
        // moteur fait le travail, l'écran garde l'ancienne liste, et rien n'échoue. La
        // deuxième fois dit que le défaut n'est pas dans la commande, il est dans le fait
        // qu'annoncer soit à la charge de celui qui écrit la commande.
        //
        // Une empreinte n'est pas une liste à tenir à jour : une commande écrite demain, à
        // laquelle personne n'aura pensé ici, sera annoncée quand même.
        let before = self.scene_contents_fingerprint();
        match event {
            EngineEvent::Exit => event_loop.exit(),
            EngineEvent::StartStream => self.handle_start_stream(),
            EngineEvent::StopStream => self.handle_stop_stream(),
            EngineEvent::StartMultistream { targets } => self.handle_start_multistream(targets),
            EngineEvent::StopMultistream => self.handle_stop_multistream(),
            EngineEvent::AddCamera { device_id, scene } => self.handle_add_camera(device_id, scene),
            EngineEvent::SetBackgroundRemoval { device_id, scene, enabled } => self.handle_set_background_removal(device_id, scene, enabled),
            EngineEvent::SetCircleMask { device_id, scene, enabled } => self.handle_set_circle_mask(device_id, scene, enabled),
            EngineEvent::RemoveCamera { device_id, scene } => self.handle_remove_camera(device_id, scene),
            EngineEvent::RestartCamera { device_id } => self.handle_restart_camera(device_id),
            EngineEvent::NudgeCamera { device_id, scene, dx, dy } => self.handle_nudge_camera(device_id, scene, dx, dy),
            EngineEvent::ScaleCamera { device_id, scene, grow } => self.handle_scale_camera(device_id, scene, grow),
            EngineEvent::CreateScene { name } => self.handle_create_scene(name),
            EngineEvent::SwitchScene { name, duration_ms } => self.handle_switch_scene(name, duration_ms),
            EngineEvent::DeleteScene { name } => self.handle_delete_scene(name),
            EngineEvent::ListAudioDevices => self.handle_list_audio_devices(),
            EngineEvent::AddAudioSource { device_id, kind, name } => {
                self.handle_add_audio_source(device_id, kind, name)
            }
            EngineEvent::RemoveAudioSource { name } => self.handle_remove_audio_source(name),
            EngineEvent::SetAudioVolume { name, percent } => {
                self.handle_set_audio_volume(name, percent)
            }
            EngineEvent::SetAudioMuted { name, muted } => self.handle_set_audio_muted(name, muted),
            EngineEvent::SetAudioMonitoring { name, monitoring } => {
                self.handle_set_audio_monitoring(name, monitoring)
            }
            EngineEvent::SetNoiseSettings { name, enabled, method, level_db } => {
                self.handle_set_noise_settings(name, enabled, method, level_db)
            }
            EngineEvent::SetMonitorVolume { name, percent } => {
                self.handle_set_monitor_volume(name, percent)
            }
            EngineEvent::ListCaptureTargets => self.handle_list_capture_targets(),
            EngineEvent::AddCaptureSource { scene, kind, target_id, name } => {
                self.handle_add_capture_source(scene, kind, target_id, name)
            }
            EngineEvent::RemoveSource { scene, name } => self.handle_remove_source(scene, name),
            EngineEvent::ReorderSource { scene, name, direction } => {
                self.handle_reorder_source(scene, name, direction)
            }
            EngineEvent::SetSourceTransform { scene, name, x, y, scale_percent } => {
                self.handle_set_source_transform(scene, name, x, y, scale_percent)
            }
            EngineEvent::SetSourceLocked { scene, name, locked } => {
                self.handle_set_source_locked(scene, name, locked)
            }
            EngineEvent::SetSourceVisible { scene, name, visible } => {
                self.handle_set_source_visible(scene, name, visible)
            }
            EngineEvent::SetTextSettings { scene, name, settings } => {
                self.handle_set_text_settings(scene, name, &settings)
            }
            EngineEvent::SetTextContent { scene, name, text } => {
                self.handle_set_text_content(scene, name, &text)
            }
            EngineEvent::RequestSceneList => {
                self.emit_scene_list();
                // Le mixeur aussi (2026-09-08) : une fenêtre rechargée sans que le moteur
                // redémarre n'a aucune autre façon de retrouver ce qu'elle affichait.
                self.emit_audio_sources();
            }
        }
        // La composition a changé sans que la commande le dise : le dire à sa place.
        if self.scene_contents_fingerprint() != before {
            self.emit_scene_list();
        }
    }

    fn about_to_wait(&mut self, event_loop: &ActiveEventLoop) {
        // Periodic reporting: frame drops while streaming (B2a: continuous health, not the
        // spike's single end-of-run sample), audio levels while the mixer holds sources
        // (B6), and the camera glide while one is in flight (B7, option A). Fully idle — no
        // stream, no multistream, no audio, no glide — never wakes the loop.
        let has_audio = self.obs.as_ref().is_some_and(|obs| !obs.audio.is_empty());
        let has_slide = self.camera_slide.is_some();
        if has_slide {
            self.advance_camera_slide();
        }
        if self.stream.is_none() && self.multistream.is_empty() && !has_audio && !has_slide {
            event_loop.set_control_flow(ControlFlow::Wait);
            return;
        }
        if self.obs.is_none() {
            return;
        }
        if let Some(stream) = &mut self.stream {
            if stream.last_stats_at.elapsed() >= FRAME_STATS_INTERVAL {
                let obs = self.obs.as_ref().expect("obs checked just above");
                report_frame_stats(&obs.context, &stream.output);
                stream.last_stats_at = Instant::now();
            }
        }
        if !self.multistream.is_empty() && self.multistream_last_stats_at.elapsed() >= FRAME_STATS_INTERVAL {
            let obs = self.obs.as_ref().expect("obs checked just above");
            for platform_stream in &self.multistream {
                report_platform_frame_stats(&obs.context, platform_stream);
            }
            self.multistream_last_stats_at = Instant::now();
        }
        if has_audio && self.audio_last_levels_at.elapsed() >= AUDIO_LEVEL_INTERVAL {
            self.emit_audio_levels();
            self.audio_last_levels_at = Instant::now();
        }
        // Wake on the SHORTEST pending deadline: a glide in flight is far more frequent
        // than the audio meter, which is itself far more frequent than the frame counters
        // — sleeping for a longer one would make the faster one visibly stutter.
        let next = if has_slide {
            CAMERA_SLIDE_TICK
        } else if has_audio {
            AUDIO_LEVEL_INTERVAL
        } else {
            FRAME_STATS_INTERVAL
        };
        event_loop.set_control_flow(ControlFlow::WaitUntil(Instant::now() + next));
    }

    fn exiting(&mut self, _event_loop: &ActiveEventLoop) {
        self.handle_stop_stream();
        self.handle_stop_multistream();
        // Explicit removal BEFORE the struct drops (belt-and-braces: field order already
        // fixed above, this also detaches the display from libobs's registry cleanly).
        if let Some(inner) = &mut self.obs {
            let _ = inner.context.remove_display(&inner.display);
        }
        self.obs = None;
        emit(&EngineMessage::Stopped);
    }

    fn window_event(&mut self, event_loop: &ActiveEventLoop, _id: WindowId, event: WindowEvent) {
        match event {
            WindowEvent::CloseRequested => event_loop.exit(),
            WindowEvent::RedrawRequested => {
                if let Some(w) = &self.window {
                    w.0.request_redraw();
                }
            }
            WindowEvent::Resized(size) => {
                let (w, h) = fit_size(size.width, size.height);
                // Kept even when libobs isn't up yet: it is the divisor every later cursor
                // conversion uses, and a stale value would misplace the camera silently.
                self.fitted = (w, h);
                if let Some(obs) = &self.obs {
                    let _ = obs.display.set_size(w, h);
                }
            }
            WindowEvent::CursorMoved { position, .. } => {
                self.cursor = Some((position.x as f32, position.y as f32));
                if self.drag.is_some() {
                    self.continue_drag();
                } else {
                    self.update_cursor_icon();
                }
            }
            WindowEvent::MouseInput { state, button: MouseButton::Left, .. } => match state {
                ElementState::Pressed => self.begin_drag(),
                ElementState::Released => {
                    self.drag = None;
                    // The camera may have ended up under a different part of the cursor.
                    self.update_cursor_icon();
                }
            },
            // The cursor leaving the preview ends the gesture: without this, coming back in
            // would teleport the camera by the distance travelled outside.
            WindowEvent::CursorLeft { .. } => self.drag = None,
            _ => (),
        }
    }
}
