//! Audio mixer (B6, tranche 1) — microphones and desktop audio as libobs sources, with
//! volume, mute, and a live level meter.
//!
//! WHY audio sources are not scene items: OBS keeps audio on its own global channels, so
//! sound survives a scene switch. Hikari does the same — a microphone belongs to the
//! session, not to whichever scene happens to be live. Channel 0 is the scene's video
//! (`switch_scene`), so audio uses channels 1 and up.
//!
//! Source ids (`wasapi_input_capture`, `wasapi_output_capture`) and the `device_id` property
//! come from the real win-wasapi plugin source, verified 2026-08-04, never guessed.

use anyhow::{Context, Result};
use hikari_protocol::{AudioDevice, AudioSourceKind};
use libobs_wrapper::context::ObsContext;
use libobs_wrapper::data::object::ObsObjectTrait;
use libobs_wrapper::data::properties::types::ObsListItemValue;
use libobs_wrapper::data::properties::{ObsProperty, ObsPropertyObject};
use libobs_wrapper::data::{ObsData, ObsDataSetters};
use libobs_wrapper::sources::{ObsFilterRef, ObsSourceBuilder, ObsSourceRef, ObsSourceTrait};
use libobs_wrapper::sys as libobs;
use libobs_simple::define_object_manager;
use std::sync::Arc;
use std::sync::atomic::{AtomicU32, Ordering};

define_object_manager!(
    #[derive(Debug)]
    /// A Windows audio capture source — the same one OBS registers for both a microphone
    /// (`wasapi_input_capture`) and desktop sound (`wasapi_output_capture`). One struct for
    /// both: they differ only by the id passed at build time.
    struct WasapiSource("wasapi_input_capture", *mut libobs::obs_source) for ObsSourceRef {
        /// The exact device identifier libobs lists, never hand-built.
        #[obs_property(type_t = "string")]
        device_id: String,
    }
);

impl ObsSourceBuilder for WasapiSourceBuilder {
    type T = ObsSourceRef;

    fn build(self) -> Result<Self::T, libobs_wrapper::utils::ObsError> {
        use libobs_wrapper::data::ObsObjectBuilder;
        let runtime = self.runtime.clone();
        ObsSourceRef::new_from_info(self.object_build()?, runtime)
    }
}

/// The first libobs channel audio may use. Channel 0 carries the live scene's video
/// (`scenes::switch_scene`), so audio starts at 1.
pub const FIRST_AUDIO_CHANNEL: u32 = 1;

/// How many audio sources the mixer holds at once. libobs offers 64 channels; this is a
/// deliberate, generous ceiling that keeps the channel search bounded and predictable.
pub const MAX_AUDIO_SOURCES: u32 = 8;

/// Probes the real audio devices of one kind: builds a throwaway source, reads its
/// `device_id` list property, and drops it. Never a presumed device list — same approach as
/// `camera::probe_camera_devices`.
pub fn probe_audio_devices(context: &ObsContext, kind: AudioSourceKind) -> Result<Vec<AudioDevice>> {
    // Built with THIS kind's id: a microphone probe would otherwise list the speakers.
    let probe = ObsSourceRef::new(
        kind.libobs_id(),
        "hikari-audio-probe",
        None,
        None,
        context.runtime().clone(),
    )
    .context("sonde audio wasapi")?;
    let properties = probe.get_properties().context("liste des propriétés wasapi")?;

    let Some(ObsProperty::List(list)) = properties.get("device_id") else {
        return Ok(Vec::new());
    };
    Ok(list
        .items()
        .iter()
        .filter_map(|item| match item.value() {
            ObsListItemValue::String(device_id) => {
                Some(AudioDevice { name: item.name().clone(), device_id: device_id.clone() })
            }
            _ => None,
        })
        .collect())
}

/// Builds an audio capture source for `device_id` on the given side, named `name`.
pub fn build_audio_source(
    context: &mut ObsContext,
    kind: AudioSourceKind,
    device_id: &str,
    name: &str,
) -> Result<ObsSourceRef> {
    let mut settings = ObsData::new(context.runtime().clone()).context("réglages source audio")?;
    settings.set_string("device_id", device_id).context("réglage périphérique audio")?;
    // The macro above bakes in the input id, so the kind is applied here instead — one
    // struct, two libobs ids.
    ObsSourceRef::new(kind.libobs_id(), name, Some(settings.into()), None, context.runtime().clone())
        .context("construction source audio")
}

/// Puts `source` on an output channel so libobs actually mixes it into the stream. Without
/// this the source exists but is silent — it is the audio equivalent of adding an item to a
/// scene.
pub fn attach_to_channel(source: &ObsSourceRef, channel: u32) -> Result<()> {
    let runtime = source.runtime().clone();
    let ptr = source.as_ptr();
    runtime
        .run_with_obs_result(move || unsafe {
            // Safety: on the OBS thread, and `ptr` comes from a live smart pointer we hold.
            libobs::obs_set_output_source(channel, ptr.get_ptr());
        })
        .context("attache de la source audio à son canal")
}

/// Frees a channel — the source stops being mixed. Called when a source leaves the mixer.
pub fn clear_channel(runtime: &libobs_wrapper::runtime::ObsRuntime, channel: u32) -> Result<()> {
    runtime
        .run_with_obs_result(move || unsafe {
            // Safety: on the OBS thread; clearing a channel is always valid.
            libobs::obs_set_output_source(channel, std::ptr::null_mut());
        })
        .context("libération du canal audio")
}

/// Sets a source's volume multiplier (0.0–1.0). `libobs-wrapper` 9.0.4 wraps no volume call
/// (checked in its source, 2026-08-04), so this dispatches the raw one, the same contract
/// `camera::set_filter_enabled` uses.
pub fn set_volume(source: &ObsSourceRef, volume: f32) -> Result<()> {
    let runtime = source.runtime().clone();
    let ptr = source.as_ptr();
    runtime
        .run_with_obs_result(move || unsafe {
            // Safety: on the OBS thread, live pointer.
            libobs::obs_source_set_volume(ptr.get_ptr(), volume);
        })
        .context("réglage du volume")
}

/// Mutes or unmutes a source. Kept distinct from a zero volume so unmuting restores the
/// slider exactly where the user left it.
pub fn set_muted(source: &ObsSourceRef, muted: bool) -> Result<()> {
    let runtime = source.runtime().clone();
    let ptr = source.as_ptr();
    runtime
        .run_with_obs_result(move || unsafe {
            // Safety: on the OBS thread, live pointer.
            libobs::obs_source_set_muted(ptr.get_ptr(), muted);
        })
        .context("sourdine")
}

/// Creates the room-noise suppression filter on `source` and attaches it DISABLED.
///
/// Same create-once-then-toggle contract as the camera filters: rebuilding a filter to turn
/// it on would interrupt the sound. Id and method come from the real obs-filters plugin
/// source (verified 2026-08-04), never guessed. RNNoise deliberately: it has no level to
/// tune, so the feature is one switch rather than a dial nobody knows how to set.
pub fn create_noise_suppression_filter(source: &ObsSourceRef) -> Result<ObsFilterRef> {
    let runtime = source.runtime().clone();
    let mut settings = ObsData::new(runtime.clone()).context("réglages suppression de bruit")?;
    settings
        .set_string("method", hikari_protocol::NOISE_SUPPRESS_METHOD)
        .context("réglage méthode de suppression")?;
    let filter = ObsFilterRef::new(
        hikari_protocol::NOISE_SUPPRESS_FILTER_KIND,
        "Suppression de bruit",
        Some(settings.into()),
        None,
        runtime,
    )
    .context("création filtre suppression de bruit")?;
    source.apply_filter(&filter).context("attache filtre suppression de bruit")?;
    crate::filters::set_enabled(&filter, false)
        .context("désactivation initiale du filtre de bruit")?;
    Ok(filter)
}

/// Sets whether the streamer hears this source, and whether the audience does.
pub fn set_monitoring(source: &ObsSourceRef, monitoring: hikari_protocol::AudioMonitoring) -> Result<()> {
    use hikari_protocol::AudioMonitoring;
    let value = match monitoring {
        AudioMonitoring::None => libobs::obs_monitoring_type_OBS_MONITORING_TYPE_NONE,
        AudioMonitoring::MonitorOnly => libobs::obs_monitoring_type_OBS_MONITORING_TYPE_MONITOR_ONLY,
        AudioMonitoring::MonitorAndOutput => {
            libobs::obs_monitoring_type_OBS_MONITORING_TYPE_MONITOR_AND_OUTPUT
        }
    };
    let runtime = source.runtime().clone();
    let ptr = source.as_ptr();
    runtime
        .run_with_obs_result(move || unsafe {
            // Safety: on the OBS thread, live pointer.
            libobs::obs_source_set_monitoring_type(ptr.get_ptr(), value);
        })
        .context("réglage de l'écoute")
}

/// Points libobs's monitoring at the system's default playback device.
///
/// WHY it must be called at all: libobs starts with NO monitoring device, so
/// `set_monitoring` would silently produce nothing — the setting would be accepted and
/// nothing would be heard, the worst kind of failure. Called once at startup.
pub fn use_default_monitoring_device(runtime: &libobs_wrapper::runtime::ObsRuntime) -> Result<()> {
    runtime
        .run_with_obs_result(move || unsafe {
            // "default" is the id libobs itself reserves for the system default device.
            let name = std::ffi::CString::new("Default").expect("literal has no interior nul");
            let id = std::ffi::CString::new("default").expect("literal has no interior nul");
            // Safety: on the OBS thread; both strings outlive the call.
            libobs::obs_set_audio_monitoring_device(name.as_ptr(), id.as_ptr())
        })
        .context("choix du périphérique d'écoute")?;
    Ok(())
}

/// A live level meter attached to one source.
///
/// libobs calls `on_level` from its own AUDIO thread, several times a second. The reading
/// therefore lands in an atomic rather than a lock: an audio callback that blocks on a mutex
/// held by the UI thread is a classic source of crackling. The engine's periodic tick reads
/// the last value whenever it likes.
pub struct LevelMeter {
    volmeter: SendPtr,
    /// Shared with the C callback. `Arc` keeps it alive while libobs may still call back;
    /// the raw pointer handed to libobs is derived from this exact allocation.
    magnitude: Arc<AtomicU32>,
}

/// A raw libobs pointer we own and destroy ourselves. Wrapped so `LevelMeter` can be stored
/// in the engine's normal state despite libobs's C pointers not being `Send` by default —
/// every use goes through the OBS thread, exactly like the wrapper's own smart pointers.
struct SendPtr(*mut libobs::obs_volmeter_t);
// Safety: the pointer is only ever dereferenced inside `run_with_obs_result`, i.e. on the
// OBS thread that created it. Nothing else touches it.
unsafe impl Send for SendPtr {}

/// The C callback libobs invokes with fresh readings. Stores channel 0's magnitude.
///
/// # Safety
/// `param` must be the `Arc<AtomicU32>` pointer `LevelMeter::attach` leaked, and `magnitude`
/// must point to at least one float — both guaranteed by libobs's own contract.
unsafe extern "C" fn on_level(
    param: *mut std::ffi::c_void,
    magnitude: *const f32,
    _peak: *const f32,
    _input_peak: *const f32,
) {
    if param.is_null() || magnitude.is_null() {
        return;
    }
    unsafe {
        let slot = &*(param as *const AtomicU32);
        // Channel 0 is enough for a mixer bar: a stereo pair moves together, and the panel
        // shows one bar per source, not per channel.
        slot.store((*magnitude).to_bits(), Ordering::Relaxed);
    }
}

impl LevelMeter {
    /// Creates a meter and attaches it to `source`. Returns `None` if libobs refuses — a
    /// missing meter costs a bar, never the sound itself, so it is not a fatal error.
    pub fn attach(source: &ObsSourceRef) -> Result<Self> {
        let magnitude = Arc::new(AtomicU32::new(f32::NEG_INFINITY.to_bits()));
        let callback_param = Arc::as_ptr(&magnitude) as *mut std::ffi::c_void;
        let source_ptr = source.as_ptr();
        let runtime = source.runtime().clone();
        let param = SendUsize(callback_param as usize);
        let volmeter = runtime
            .run_with_obs_result(move || unsafe {
                // Safety: on the OBS thread. `obs_fader_type_OBS_FADER_LOG` is the scale OBS
                // itself uses for its mixer meters.
                let volmeter = libobs::obs_volmeter_create(libobs::obs_fader_type_OBS_FADER_LOG);
                if volmeter.is_null() {
                    return 0usize;
                }
                libobs::obs_volmeter_attach_source(volmeter, source_ptr.get_ptr());
                libobs::obs_volmeter_add_callback(volmeter, Some(on_level), param.0 as *mut _);
                volmeter as usize
            })
            .context("création du mesureur de niveau")?;
        if volmeter == 0 {
            anyhow::bail!("libobs a refusé de créer le mesureur de niveau");
        }
        Ok(Self { volmeter: SendPtr(volmeter as *mut libobs::obs_volmeter_t), magnitude })
    }

    /// The last reading, in decibels. `-inf` until the first callback arrives.
    pub fn magnitude_db(&self) -> f32 {
        f32::from_bits(self.magnitude.load(Ordering::Relaxed))
    }

    /// Detaches and destroys the meter. Explicit rather than a `Drop` impl: destroying a
    /// libobs object must happen on the OBS thread, and `Drop` cannot be handed a runtime.
    /// The callback is removed BEFORE the shared slot can be freed, so libobs can never call
    /// back into released memory.
    pub fn destroy(self, runtime: &libobs_wrapper::runtime::ObsRuntime) -> Result<()> {
        let volmeter = self.volmeter;
        let param = SendUsize(Arc::as_ptr(&self.magnitude) as usize);
        runtime
            .run_with_obs_result(move || unsafe {
                // Bind the WHOLE wrapper first. Rust 2021 closures capture disjoint fields,
                // so writing `volmeter.0` alone would capture the raw pointer itself — which
                // is not `Send` — instead of the `SendPtr` that is.
                let volmeter = volmeter;
                // Safety: on the OBS thread; the pointer was created there and not yet freed.
                libobs::obs_volmeter_remove_callback(
                    volmeter.0,
                    Some(on_level),
                    param.0 as *mut _,
                );
                libobs::obs_volmeter_detach_source(volmeter.0);
                libobs::obs_volmeter_destroy(volmeter.0);
            })
            .context("destruction du mesureur de niveau")?;
        // `self.magnitude` drops here, after the callback is provably unregistered.
        Ok(())
    }
}

/// A pointer-sized value moved onto the OBS thread. A raw pointer is not `Send`; the address
/// itself is just a number, and it is turned back into a pointer only on the OBS thread.
struct SendUsize(usize);
// Safety: carries an address, dereferenced only on the OBS thread by the closures above.
unsafe impl Send for SendUsize {}
