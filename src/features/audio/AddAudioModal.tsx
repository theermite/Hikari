// Le choix d'une piste à ajouter au mixeur — sur DEMANDE, jamais étalé en permanence.
//
// Ce que ça remplace : les deux listes complètes des micros et des sorties, dépliées en
// bas du mixeur à longueur de temps. Jay, 2026-09-05 : « faire des listes à rallonge comme
// ça n'est pas intuitif, c'est gaspiller de l'espace et forcer du scroll, alors qu'un petit
// bouton clair sur l'intention est bien plus efficace ».
//
// Sa machine expose une douzaine de périphériques ; les montrer tous, tout le temps,
// remplissait le panneau d'un choix qu'on ne fait qu'une fois par appareil.

import { Modal } from "../../components/Modal";
import { SectionTitle } from "../../components/ui/SectionTitle";
import type { AudioDevice, AudioSourceKind } from "./types";

interface AddAudioModalProps {
  open: boolean;
  /** Micros encore absents du mixeur. */
  inputs: AudioDevice[];
  /** Sorties (son du bureau) encore absentes du mixeur. */
  outputs: AudioDevice[];
  busy: boolean;
  onClose: () => void;
  onAdd: (device: AudioDevice, kind: AudioSourceKind) => void;
}

function DeviceGroup({
  title,
  devices,
  emptyLabel,
  busy,
  onPick,
}: {
  title: string;
  devices: AudioDevice[];
  emptyLabel: string;
  busy: boolean;
  onPick: (device: AudioDevice) => void;
}) {
  return (
    <div className="flex flex-col gap-1.5">
      <SectionTitle level={4}>{title}</SectionTitle>
      {devices.length === 0 ? (
        <p className="text-[12px] text-hikari-txt-faint">{emptyLabel}</p>
      ) : (
        <ul className="flex flex-col gap-1">
          {devices.map((device) => (
            <li key={device.device_id}>
              <button
                type="button"
                onClick={() => onPick(device)}
                disabled={busy}
                className="w-full truncate rounded-[6px] border border-hikari-line px-2.5 py-1.5 text-left text-[12.5px] text-hikari-txt-dim transition hover:border-hikari-accent hover:text-hikari-txt disabled:opacity-50"
              >
                {device.name}
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

export function AddAudioModal({
  open,
  inputs,
  outputs,
  busy,
  onClose,
  onAdd,
}: AddAudioModalProps) {
  // La fenêtre se ferme au choix : ajouter une piste est un geste unique, et rester ouvert
  // obligerait à un second clic pour rien.
  const pick = (device: AudioDevice, kind: AudioSourceKind) => {
    onAdd(device, kind);
    onClose();
  };

  return (
    <Modal open={open} title="Ajouter une piste au mixeur" onClose={onClose}>
      <div className="flex flex-col gap-4">
        <DeviceGroup
          title="Micros"
          devices={inputs}
          emptyLabel="Tous tes micros sont déjà dans le mixeur."
          busy={busy}
          onPick={(device) => pick(device, "input")}
        />
        <DeviceGroup
          title="Sons du bureau"
          devices={outputs}
          emptyLabel="Toutes tes sorties sont déjà dans le mixeur."
          busy={busy}
          onPick={(device) => pick(device, "output")}
        />
      </div>
    </Modal>
  );
}
