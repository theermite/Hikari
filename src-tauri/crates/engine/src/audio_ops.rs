//! The audio mixer (B6): listing devices, adding/removing entries, volumes, mute, routing,
//! noise suppression, and the level meter tick — the audio group of `App`'s command
//! handlers.

use hikari_protocol::EngineMessage;

use crate::{App, LiveCapture, MixerSource, audio, emit, filters};

impl App {
    /// Emits the machine's real audio devices, both sides (B6). A failure on one side is
    /// reported and yields an empty list for that side rather than hiding the other.
    pub(crate) fn handle_list_audio_devices(&mut self) {
        let Some(obs) = &mut self.obs else {
            emit(&EngineMessage::Error { message: "ListAudioDevices avant l'initialisation".into() });
            return;
        };
        let probe = |kind| match audio::probe_audio_devices(&obs.context, kind) {
            Ok(devices) => devices,
            Err(err) => {
                emit(&EngineMessage::Error { message: err.to_string() });
                Vec::new()
            }
        };
        let inputs = probe(hikari_protocol::AudioSourceKind::Input);
        let outputs = probe(hikari_protocol::AudioSourceKind::Output);
        emit(&EngineMessage::AudioDevices { inputs, outputs });
    }

    /// Adds a microphone or desktop-audio capture to the mixer (B6).
    pub(crate) fn handle_add_audio_source(
        &mut self,
        device_id: String,
        kind: hikari_protocol::AudioSourceKind,
        name: String,
    ) {
        let Some(obs) = &mut self.obs else {
            emit(&EngineMessage::Error { message: "AddAudioSource avant l'initialisation".into() });
            return;
        };
        if obs.audio.iter().any(|existing| existing.name == name) {
            emit(&EngineMessage::Error { message: format!("« {name} » est déjà dans le mixeur") });
            return;
        }
        let Some(channel) = Self::free_audio_channel(&obs.audio) else {
            emit(&EngineMessage::Error {
                message: format!("mixeur plein ({} sources maximum)", audio::MAX_AUDIO_SOURCES),
            });
            return;
        };
        let capture = match self.open_capture(&device_id, kind, &name, channel) {
            Some(capture) => capture,
            None => return,
        };
        let Some(obs) = &mut self.obs else { return };
        // A missing meter costs a bar, never the sound — reported, then carried on without.
        let meter = match audio::LevelMeter::attach(&capture.source) {
            Ok(meter) => Some(meter),
            Err(err) => {
                emit(&EngineMessage::Error { message: err.to_string() });
                None
            }
        };
        obs.audio.push(MixerSource {
            name,
            kind,
            public: Some(capture),
            monitor: None,
            meter,
            // libobs starts a source at unity gain; the slider must say the same thing the
            // ear hears, so it starts at 100 rather than at some remembered default.
            volume_percent: 100,
            monitor_volume_percent: 100,
            muted: false,
            // libobs's own default, and the safe one: monitoring a microphone through
            // speakers is how a feedback howl starts.
            monitoring: hikari_protocol::AudioMonitoring::None,
            noise_suppression: false,
            noise_method: hikari_protocol::NoiseMethod::Rnnoise,
            noise_level_db: hikari_protocol::NOISE_LEVEL_DEFAULT_DB,
            device_id,
        });
        self.emit_audio_sources();
    }

    /// Opens ONE libobs capture of `device_id` on `channel`, with its noise filter attached
    /// disabled where that means something. `None` (after reporting) if libobs refused —
    /// which is the case a second capture of the same device can genuinely hit.
    fn open_capture(
        &mut self,
        device_id: &str,
        kind: hikari_protocol::AudioSourceKind,
        libobs_name: &str,
        channel: u32,
    ) -> Option<LiveCapture> {
        let obs = self.obs.as_mut()?;
        let source = match audio::build_audio_source(&mut obs.context, kind, device_id, libobs_name)
        {
            Ok(source) => source,
            Err(err) => {
                emit(&EngineMessage::Error { message: err.to_string() });
                return None;
            }
        };
        if let Err(err) = audio::attach_to_channel(&source, channel) {
            emit(&EngineMessage::Error { message: err.to_string() });
            return None;
        }
        // Attached disabled, only where it means something. A failure costs the feature on
        // this capture, never the capture itself — the microphone still works without it.
        let noise_filter = if kind.supports_noise_suppression() {
            match audio::create_noise_suppression_filter(&source) {
                Ok(filter) => Some(filter),
                Err(err) => {
                    emit(&EngineMessage::Error { message: err.to_string() });
                    None
                }
            }
        } else {
            None
        };
        Some(LiveCapture { source, channel, noise_filter })
    }

    /// The lowest channel no capture occupies. `None` when the mixer is full. Counts every
    /// capture, not every entry — an entry heard by both sides holds two.
    fn free_audio_channel(sources: &[MixerSource]) -> Option<u32> {
        (audio::FIRST_AUDIO_CHANNEL..audio::FIRST_AUDIO_CHANNEL + audio::MAX_AUDIO_SOURCES).find(
            |channel| {
                !sources
                    .iter()
                    .flat_map(MixerSource::captures)
                    .any(|capture| capture.channel == *channel)
            },
        )
    }

    /// Frees one capture's channel. The capture itself drops with its owner.
    fn close_capture(runtime: &libobs_wrapper::runtime::ObsRuntime, capture: &LiveCapture) {
        if let Err(err) = audio::clear_channel(runtime, capture.channel) {
            emit(&EngineMessage::Error { message: err.to_string() });
        }
    }

    /// Removes an entry from the mixer: destroys its meter, frees every capture it holds.
    pub(crate) fn handle_remove_audio_source(&mut self, name: String) {
        let Some(obs) = &mut self.obs else { return };
        let Some(index) = obs.audio.iter().position(|source| source.name == name) else {
            emit(&EngineMessage::Error { message: format!("« {name} » n'est pas dans le mixeur") });
            return;
        };
        let mut removed = obs.audio.remove(index);
        let runtime = obs.context.runtime().clone();
        // The meter goes first: it must stop pointing at a source about to be freed. Taken
        // out of the entry so the captures below can still be read from it.
        if let Some(meter) = removed.meter.take() {
            if let Err(err) = meter.destroy(&runtime) {
                emit(&EngineMessage::Error { message: err.to_string() });
            }
        }
        for capture in removed.captures() {
            Self::close_capture(&runtime, capture);
        }
        self.emit_audio_sources();
    }

    /// Sets the volume the AUDIENCE hears. A muted entry keeps the new value: it takes
    /// effect the moment it is unmuted, never silently discarded.
    pub(crate) fn handle_set_audio_volume(&mut self, name: String, percent: i32) {
        self.update_entry(&name, |entry| {
            entry.volume_percent =
                hikari_protocol::volume_to_percent(hikari_protocol::percent_to_volume(percent));
        });
    }

    /// Sets the volume the STREAMER hears, independently of the audience's.
    pub(crate) fn handle_set_monitor_volume(&mut self, name: String, percent: i32) {
        self.update_entry(&name, |entry| {
            entry.monitor_volume_percent =
                hikari_protocol::volume_to_percent(hikari_protocol::percent_to_volume(percent));
        });
    }

    /// Mutes or unmutes an entry, leaving its sliders untouched.
    pub(crate) fn handle_set_audio_muted(&mut self, name: String, muted: bool) {
        self.update_entry(&name, |entry| entry.muted = muted);
    }

    /// Sets room-noise suppression: on/off, method, and Speex's strength.
    pub(crate) fn handle_set_noise_settings(
        &mut self,
        name: String,
        enabled: bool,
        method: hikari_protocol::NoiseMethod,
        level_db: f32,
    ) {
        self.update_entry(&name, |entry| {
            entry.noise_suppression = enabled;
            entry.noise_method = method;
            entry.noise_level_db = hikari_protocol::clamp_noise_level(level_db);
        });
    }

    /// Applies a change to one entry, then re-pushes ITS WHOLE desired state to libobs.
    ///
    /// Re-applying everything rather than only what changed is deliberate: routing decides
    /// which capture carries which volume, so a volume change and a routing change touch the
    /// same libobs calls. One place that reconciles the whole entry cannot drift; five places
    /// that each patch one field eventually do.
    fn update_entry(&mut self, name: &str, change: impl FnOnce(&mut MixerSource)) {
        let Some(obs) = &mut self.obs else { return };
        let Some(index) = obs.audio.iter().position(|source| source.name == name) else {
            emit(&EngineMessage::Error { message: format!("« {name} » n'est pas dans le mixeur") });
            return;
        };
        change(&mut obs.audio[index]);
        self.reconcile_entry(index);
        self.emit_audio_sources();
    }

    /// Sets whether the streamer hears this entry, and whether the audience does.
    ///
    /// This is the call that may open or close the SECOND capture: "both hear it" needs two
    /// (one per volume), the two one-sided modes need one.
    pub(crate) fn handle_set_audio_monitoring(
        &mut self,
        name: String,
        monitoring: hikari_protocol::AudioMonitoring,
    ) {
        self.update_entry(&name, |entry| entry.monitoring = monitoring);
    }

    /// Makes libobs match one entry's desired state — captures, volumes, mute, filters.
    fn reconcile_entry(&mut self, index: usize) {
        use hikari_protocol::AudioMonitoring;
        let Some(obs) = &mut self.obs else { return };
        let Some(entry) = obs.audio.get(index) else { return };
        let (wants_public, wants_monitor) = match entry.monitoring {
            AudioMonitoring::None => (true, false),
            AudioMonitoring::MonitorOnly => (false, true),
            AudioMonitoring::MonitorAndOutput => (true, true),
        };
        let runtime = obs.context.runtime().clone();
        let (name, device_id, kind) =
            (entry.name.clone(), entry.device_id.clone(), entry.kind);

        // Close what is no longer wanted BEFORE opening what is: a device that refuses two
        // simultaneous captures would otherwise fail on a mere routing change.
        for (wanted, take) in [
            (wants_public, true),
            (wants_monitor, false),
        ] {
            if wanted {
                continue;
            }
            let Some(obs) = &mut self.obs else { return };
            let Some(entry) = obs.audio.get_mut(index) else { return };
            let slot = if take { &mut entry.public } else { &mut entry.monitor };
            if let Some(capture) = slot.take() {
                Self::close_capture(&runtime, &capture);
            }
        }

        // Open what is missing. A refusal is reported and leaves the entry one-sided rather
        // than silently pretending both volumes are live.
        for (wanted, is_public) in [(wants_public, true), (wants_monitor, false)] {
            let already = self
                .obs
                .as_ref()
                .and_then(|obs| obs.audio.get(index))
                .is_some_and(|entry| if is_public { entry.public.is_some() } else { entry.monitor.is_some() });
            if !wanted || already {
                continue;
            }
            let Some(channel) =
                Self::free_audio_channel(self.obs.as_ref().map_or(&[], |obs| &obs.audio))
            else {
                emit(&EngineMessage::Error {
                    message: format!("mixeur plein ({} canaux)", audio::MAX_AUDIO_SOURCES),
                });
                continue;
            };
            // The second capture needs its own libobs name — two sources cannot share one.
            let libobs_name =
                if is_public { name.clone() } else { format!("{name} (retour)") };
            let Some(capture) = self.open_capture(&device_id, kind, &libobs_name, channel) else {
                continue;
            };
            let Some(obs) = &mut self.obs else { return };
            let Some(entry) = obs.audio.get_mut(index) else { return };
            if is_public {
                entry.public = Some(capture);
            } else {
                entry.monitor = Some(capture);
            }
        }

        self.apply_entry_settings(index);
    }

    /// Pushes an entry's volumes, mute and filter state onto whichever captures now exist.
    fn apply_entry_settings(&mut self, index: usize) {
        use hikari_protocol::AudioMonitoring;
        let Some(obs) = &mut self.obs else { return };
        let Some(entry) = obs.audio.get(index) else { return };
        let public_volume = hikari_protocol::percent_to_volume(entry.volume_percent);
        let monitor_volume = hikari_protocol::percent_to_volume(entry.monitor_volume_percent);
        let (muted, enabled, method, level_db) =
            (entry.muted, entry.noise_suppression, entry.noise_method, entry.noise_level_db);

        let apply = |capture: &LiveCapture, volume: f32, routing: AudioMonitoring| {
            if let Err(err) = audio::set_volume(&capture.source, volume) {
                emit(&EngineMessage::Error { message: err.to_string() });
            }
            if let Err(err) = audio::set_muted(&capture.source, muted) {
                emit(&EngineMessage::Error { message: err.to_string() });
            }
            if let Err(err) = audio::set_monitoring(&capture.source, routing) {
                emit(&EngineMessage::Error { message: err.to_string() });
            }
            if let Some(filter) = &capture.noise_filter {
                if let Err(err) = audio::apply_noise_settings(filter, method, level_db) {
                    emit(&EngineMessage::Error { message: err.to_string() });
                }
                if let Err(err) = filters::set_enabled(filter, enabled) {
                    emit(&EngineMessage::Error { message: err.to_string() });
                }
            }
        };

        if let Some(capture) = &entry.public {
            // The public capture is never played back: the monitor capture does that job.
            apply(capture, public_volume, AudioMonitoring::None);
        }
        if let Some(capture) = &entry.monitor {
            // Always the headphone slider — whether this capture is the entry's only one
            // (streamer listens alone) or its second (both listen).
            apply(capture, monitor_volume, AudioMonitoring::MonitorOnly);
        }
    }

    /// Emits the mixer's real state — shared tail of every command that changes it.
    fn emit_audio_sources(&mut self) {
        let Some(obs) = &mut self.obs else { return };
        let items = obs
            .audio
            .iter()
            .map(|source| hikari_protocol::AudioSourceInfo {
                name: source.name.clone(),
                kind: source.kind,
                device_id: source.device_id.clone(),
                volume_percent: source.volume_percent,
                monitor_volume_percent: source.monitor_volume_percent,
                muted: source.muted,
                monitoring: source.monitoring,
                noise_suppression: source.noise_suppression,
                noise_method: source.noise_method,
                noise_level_db: source.noise_level_db,
            })
            .collect();
        emit(&EngineMessage::AudioSources { items });
    }

    /// Emits every source's current loudness. Called on the engine's periodic tick, never
    /// from the audio callback itself — that one only stores a number, so it never blocks.
    pub(crate) fn emit_audio_levels(&mut self) {
        let Some(obs) = &mut self.obs else { return };
        if obs.audio.is_empty() {
            return;
        }
        let levels = obs
            .audio
            .iter()
            .map(|source| {
                // A muted source is silent to the listener; showing its bar still moving
                // would say the opposite of what is being heard. `AudioLevel::new` turns
                // that silence into a value JSON can carry — sending `-inf` used to make
                // the whole message unreadable, freezing EVERY bar (regression 2026-08-04).
                let db = match (&source.meter, source.muted) {
                    (_, true) | (None, _) => f32::NEG_INFINITY,
                    (Some(meter), false) => meter.magnitude_db(),
                };
                hikari_protocol::AudioLevel::new(source.name.clone(), db)
            })
            .collect();
        emit(&EngineMessage::AudioLevels { levels });
    }
}
