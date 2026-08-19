//! Engine startup (`try_init`) and the stream/multistream start/stop commands — the
//! lifecycle group of `App`'s command handlers.

use anyhow::{Context, Result};
use hikari_protocol::{EngineMessage, SourceInfo};
use libobs_simple::sources::windows::MonitorCaptureSourceBuilder;
use libobs_wrapper::context::ObsContext;
use libobs_wrapper::data::output::ObsOutputTrait;
use libobs_wrapper::display::{ObsDisplayCreationData, ObsDisplayRef, ObsWindowHandle};
use libobs_wrapper::scenes::{ObsSceneItemRef, SceneItemTrait};
use libobs_wrapper::sources::ObsSourceRef;
use libobs_wrapper::unsafe_send::Sendable;
use std::time::Instant;
use winit::event_loop::ActiveEventLoop;
use winit::raw_window_handle::{HasWindowHandle, RawWindowHandle};
use winit::window::Window;

use crate::multistream::{start_multistream, stop_one};
use crate::stream::{StreamState, start_stream};
use crate::{App, MONITOR_CAPTURE_NAME, ObsInner, PREVIEW_START_HEIGHT, PREVIEW_START_WIDTH, SceneSource, emit, outline, sources};

/// Build the "main" scene with a screen capture, as an ORDINARY source.
///
/// Elle passe par le même chemin que toute source ajoutée à la main (2026-08-05) : avant, la
/// capture de démarrage était construite à part et rangée dans un champ dédié, ce qui la
/// rendait ni retirable, ni saisissable à la souris, ni listée comme les autres. Jay l'a
/// signalé — « il y a une source que je ne peux pas supprimer ». Une exception dans le
/// modèle finit toujours par se voir à l'écran.
fn build_scene_with_capture(
    context: &mut ObsContext,
) -> Result<(Vec<SourceInfo>, ObsSceneItemRef<ObsSourceRef>, String)> {
    context.scene("main", Some(0))?;
    let monitors = MonitorCaptureSourceBuilder::get_monitors()?;
    let first = monitors.first().context("no monitor available to capture")?;
    let monitor_id = first.0.name.clone();
    let item = sources::add_capture_to_scene(
        context,
        hikari_protocol::SourceKind::Monitor,
        &monitor_id,
        MONITOR_CAPTURE_NAME,
        "main",
    )?;
    // Mise au cadre : un écran 4K sur un canevas 1080p déborderait sans ça.
    item.fit_source_to_screen()?;
    Ok((vec![SourceInfo::monitor_capture(MONITOR_CAPTURE_NAME)], item, monitor_id))
}

/// Creates the preview window + its `obs_display`. Transcribed from the B1b spike
/// (jalon 1, `spikes/b1b-preview/src/main.rs`), proven GO 2026-07-18.
fn create_preview(context: &mut ObsContext, window: &Window) -> Result<ObsDisplayRef> {
    let RawWindowHandle::Win32(handle) = window.window_handle()?.as_raw() else {
        anyhow::bail!("moteur Windows uniquement : handle de fenêtre Win32 attendu");
    };
    let obs_handle = ObsWindowHandle::new_from_handle(handle.hwnd.get() as *mut _);
    let size = window.inner_size();
    let data = ObsDisplayCreationData::new(obs_handle, 0, 0, size.width, size.height);
    Ok(context.display(data)?)
}

impl App {
    /// The fallible half of initialization, isolated so `resumed()` (which winit's
    /// `ApplicationHandler` does not let return `Result`) can report a failure on the wire
    /// instead of panicking. A panic here would bypass `main()`'s `EngineMessage::Error`
    /// path entirely (regression found in review: `resumed()` used to `.expect()` these
    /// same calls, so any failure — e.g. "no monitor available", a real, documented,
    /// plausible prod error — became a silent process death, exactly the "mute failure"
    /// this file's own header warns against).
    pub(crate) fn try_init(&mut self, event_loop: &ActiveEventLoop) -> Result<()> {
        let attrs = Window::default_attributes()
            .with_title("Hikari engine — aperçu")
            .with_inner_size(winit::dpi::LogicalSize::new(PREVIEW_START_WIDTH, PREVIEW_START_HEIGHT));
        let window = event_loop.create_window(attrs).context("création fenêtre d'aperçu")?;

        let mut context = ObsContext::new(libobs_wrapper::utils::StartupInfo::default()).context("init libobs")?;
        emit(&EngineMessage::Ready);

        let (sources, scene_item, startup_monitor) =
            build_scene_with_capture(&mut context).context("construction scène")?;
        emit(&EngineMessage::Sources { items: sources.clone() });

        // Without this, libobs has NO monitoring device and "écouter" would be accepted
        // while producing nothing — a setting that lies is worse than a missing one.
        if let Err(err) = crate::audio::use_default_monitoring_device(context.runtime()) {
            emit(&EngineMessage::Error { message: err.to_string() });
        }

        let display = create_preview(&mut context, &window).context("création aperçu")?;
        // Le liseré se dessine par-dessus l'image du moteur — seul endroit possible, la
        // fenêtre native couvrant tout contenu web. Un échec coûte le contour, jamais
        // l'aperçu : signalé, puis on continue.
        if let Err(err) = outline::attach(context.runtime(), &display) {
            emit(&EngineMessage::Error { message: err.to_string() });
        }
        let RawWindowHandle::Win32(handle) = window.window_handle()?.as_raw() else {
            anyhow::bail!("moteur Windows uniquement : handle de fenêtre Win32 attendu");
        };
        emit(&EngineMessage::PreviewReady { hwnd: handle.hwnd.get() as i64 });

        self.obs = Some(ObsInner {
            display,
            context,
            sources,
            camera_source: None,
            camera_device_id: None,
            camera_filters: None,
            camera_items: std::collections::HashMap::new(),
            locked: std::collections::HashSet::new(),
            scene_filter_state: std::collections::HashMap::new(),
            active_scene: "main".to_string(),
            item_rects: None,
            audio: Vec::new(),
            // La capture de démarrage est enregistrée comme une source ORDINAIRE : c'est ce
            // qui la rend retirable, saisissable et listée au même titre que les autres.
            scene_sources: std::collections::HashMap::from([(
                "main".to_string(),
                vec![SceneSource {
                    name: MONITOR_CAPTURE_NAME.to_string(),
                    kind: hikari_protocol::MONITOR_CAPTURE_KIND.to_string(),
                    source_kind: hikari_protocol::SourceKind::Monitor,
                    target_id: startup_monitor,
                    item: scene_item,
                }],
            )]),
        });
        self.window = Some(Sendable(window));
        emit(&EngineMessage::SceneList {
            scenes: vec![hikari_protocol::SceneInfo::empty("main")],
            active: "main".to_string(),
        });
        Ok(())
    }

    /// Starts a stream if none is running yet and the engine is initialized. A second
    /// `StartStream` while one is already live is a no-op (never double-attach an output).
    pub(crate) fn handle_start_stream(&mut self) {
        let Some(obs) = &mut self.obs else {
            emit(&EngineMessage::Error { message: "StartStream avant l'initialisation".into() });
            return;
        };
        if self.stream.is_some() {
            return;
        }
        match start_stream(&mut obs.context) {
            Ok(output) => self.stream = Some(StreamState { output, last_stats_at: Instant::now() }),
            Err(err) => emit(&EngineMessage::Error { message: err.to_string() }),
        }
    }

    /// Stops the current stream, if any. A `StopStream` with nothing running is a no-op.
    pub(crate) fn handle_stop_stream(&mut self) {
        let Some(mut stream) = self.stream.take() else { return };
        if let Err(err) = stream.output.stop() {
            emit(&EngineMessage::Error { message: format!("arrêt de la diffusion: {err}") });
        }
        emit(&EngineMessage::StreamStopped);
    }

    /// Starts multistream to every target (B3): each target starts independently, a
    /// failure on one is reported (`PlatformError`) and skipped, never aborting the
    /// others. A second `StartMultistream` while one is already running is a no-op —
    /// same "never double-attach" rule as `handle_start_stream`.
    pub(crate) fn handle_start_multistream(&mut self, targets: Vec<hikari_protocol::StreamTarget>) {
        let Some(obs) = &mut self.obs else {
            emit(&EngineMessage::Error { message: "StartMultistream avant l'initialisation".into() });
            return;
        };
        if !self.multistream.is_empty() {
            return;
        }
        self.multistream = start_multistream(&mut obs.context, &targets);
    }

    /// Stops every running multistream target. A target already stopped is a no-op for
    /// that target (see `multistream::stop_one`).
    pub(crate) fn handle_stop_multistream(&mut self) {
        for mut stream in self.multistream.drain(..) {
            stop_one(&mut stream);
        }
    }
}
