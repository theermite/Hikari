"""Découpe une commande shell en ACTES: ce qu'elle fait, non ce qu'elle dit.

Pourquoi ce module existe. Deux relectures indépendantes (2026-10-26) ont refusé les garde-fous qui
jugeaient une commande par des expressions régulières sur son texte: un chemin entre guillemets, `uv run
python -c`, `env X=1 bash -c`, `git -C . commit`, un alias git, un message de commit qui cite un fichier.
Même famille deux fois: « le déclencheur lit le texte d'une commande, pas son acte ». Règle 03 § 6: au
deuxième échec de la même famille, on change de méthode. Celle-ci:

- on LIT la commande comme le shell (`shell_lecteur`): guillemets, séparateurs, heredocs, `$( )`;
- on retrouve le VRAI programme sous ses enveloppes (`env`, `sudo`, `uv run`, `time`, `cd x &&`);
- les programmes qui EXÉCUTENT une chaîne (`bash -c`, `ssh`, `xargs`, `find -exec`, `python -c`) rendent cette
  chaîne lisible: elle est une commande, pas un texte;
- la lecture seule est une liste FERMÉE de formes acceptées, jamais une liste d'exclusion (Tests-Et-Mesures:
  « mesurer une chose, jamais un mot à son sujet »);
- écrire n'est pas nommer (`actes_ecrits`), et git se lit après ses options (`actes_git`).

Limites écrites. Le code d'un interpréteur n'est pas exécuté: ses chaînes qui ressemblent à un chemin comptent
comme écrites (on sur-déclenche, jamais l'inverse). Une variable, un alias shell ou un `source` ne se résolvent
pas. Un contenu venu de l'entrée standard (`cat s | bash`) est inconnu: la commande n'est pas une lecture.

Écartés après la relecture n° 3, avec leur raison (git garde l'historique, on peut revenir dessus avec une
preuve nouvelle): `git add -A` et `git config` ne sont pas « état partagé » (l'index se garde par chemins
explicites, `bash-guard` refuse déjà `-A`; ni historique ni branche ne changent); `git fetch --prune` ne touche
que les références distantes. Une commande distante (`ssh`, `docker exec`) garde son texte pour les motifs de
mise en service mais n'écrit rien ici. Limite assumée: les tables (interpréteurs, options, sous-commandes) ne
seront jamais complètes; ce qui manque se corrige par un cas de test, pas par une expression de plus.
"""

from __future__ import annotations

import posixpath
import re
from dataclasses import dataclass, replace

import actes_ecrivains
import actes_git
import actes_inoffensifs
import shell_lecteur
from actes_ecrits import (
    chemins_du_code,
    debut_positionnels,
    ecrits_du_programme,
    neutre,
    positionnels,
    resoudre,
    valeurs_d_option,
)
from shell_lecteur import Mot, lire

PROFONDEUR_MAX = 6

_AFFECTATION = re.compile(r"^[A-Za-z_]\w*=")
_MOTS_DE_TETE = {"if", "then", "else", "elif", "do", "while", "until", "!", "{", "}"}
_ENTETES = {"for", "case", "select", "function", "fi", "done", "esac", "in"}
_ENVELOPPES = {   # programme -> options qui prennent une valeur séparée
    "command": (), "builtin": (), "exec": ("-a",), "nohup": (), "setsid": (), "winpty": (), "env": ("-u", "-C"),
    "nice": ("-n",), "ionice": ("-c", "-n", "-p"), "stdbuf": ("-i", "-o", "-e"), "caffeinate": (),
    "sudo": ("-u", "-g", "-h", "-p", "-C", "-D", "-R", "-T", "-U", "-r", "-t"), "doas": ("-u", "-C"),
    "timeout": ("-s", "-k", "--signal", "--kill-after"), "time": ("-f", "-o"),
}
_OPTIONS_UV = ("--python", "-p", "--with", "--with-requirements", "--directory", "--project", "--env-file",
               "--group", "--extra", "--package", "--index", "-w")
_SHELLS = ("bash", "sh", "zsh", "dash", "ksh", "ash")
_CODE = {   # interpréteur -> (options courtes, options longues) qui portent du code
    "node": (("-e", "-p"), ("--eval", "--print")), "bun": (("-e",), ("--eval",)), "php": (("-r",), ()),
    "elixir": (("-e",), ("--eval",)),
}
_CODE_REGEX = {"python": r"-[a-zA-Z]*c", "perl": r"-[a-zA-Z]*[eE]", "ruby": r"-[a-zA-Z]*e"}   # options groupées: `-Ic`
_POWERSHELL = ("pwsh", "powershell")      # `-Command`, `-com`, `-c`: tout préfixe de « -command » compte
_AWK = ("awk", "gawk", "mawk")
_CODE_NUS = _POWERSHELL + _AWK            # code sans guillemets autour des chemins
_SSH_VALEURS = ("-b", "-c", "-D", "-E", "-e", "-F", "-I", "-i", "-J", "-L", "-l", "-m", "-O", "-o", "-p", "-Q",
                "-R", "-S", "-W", "-w")
_DOCKER_VALEURS = ("-e", "--env", "-u", "--user", "-w", "--workdir", "--env-file")
_XARGS_VALEURS = ("-a", "-d", "-E", "-I", "-L", "-n", "-P", "-s", "-R", "-S")
_EXEC_FIND = ("-exec", "-execdir", "-ok", "-okdir")
_SORTIES_FIND = ("-fprint", "-fprint0", "-fprintf", "-fls")
_LECTURES = {   # liste FERMÉE: ces programmes ne changent rien (la redirection est jugée à part)
    "ls", "dir", "pwd", "cat", "head", "tail", "grep", "egrep", "fgrep", "rg", "wc", "which", "whereis", "type",
    "echo", "printf", "true", "false", "test", "[", "stat", "file", "diff", "cmp", "du", "df", "date", "whoami",
    "hostname", "id", "uname", "basename", "dirname", "realpath", "readlink", "nl",
    "md5sum", "sha1sum", "sha256sum", "jq", "cut", "tr", "sleep", "printenv", "cd", "pushd", "popd",
}


@dataclass(frozen=True)
class Acte:
    programme: str
    texte: str                      # forme sur laquelle s'appliquent les motifs de commande
    ecrits: tuple = ()              # chemins que l'acte écrit
    lecture: bool = False           # ne change rien
    partage: bool = False           # change l'historique, la branche ou l'arbre qu'une autre séance utilise
    inoffensif: bool = False        # test, vérification ou conteneur dont le contenu est jugé à part: n'écrit rien
    certain: bool = False           # écrivain connu (formateur, gestionnaire de paquets)
    dossier: str = ""               # où l'acte agit (`cd`, `git -C`): un geste dans un dépôt voisin n'est pas un geste d'ici


@dataclass
class _Ctx:
    prog: str
    mots: list                      # arguments, en Mot
    cwd: str
    p: int
    sortie: list
    corps: list
    ecrits: list
    brut: bool = False              # la forme garde les chaînes entre guillemets: elles s'exécutent
    lecture: bool = False
    partage: bool = False
    inoffensif: bool = False
    dossier: str | None = None
    texte: str | None = None

    @property
    def a(self) -> list[str]:
        return [m.texte for m in self.mots]


def _nom(texte: str) -> str:
    nom = re.sub(r"\.(exe|cmd|bat)$", "", texte.replace("\\", "/").rsplit("/", 1)[-1].lower())
    if re.fullmatch(r"python[\d.]*|py|pypy[\d.]*", nom):
        return "python"
    return "node" if nom == "nodejs" else nom


def _ecrit_par_redirection(op: str, cible: str) -> bool:
    if op not in (">", ">>", ">|", "&>", "&>>", ">&"):
        return False
    return not (neutre(cible) or (op == ">&" and cible.isdigit()))


# --- le premier VRAI mot: sans mots-clés, affectations ni enveloppes ----------------------------------

def _enveloppe(mots: list[Mot], nom: str) -> list[Mot]:
    reste = mots[1:]
    debut = debut_positionnels([m.texte for m in reste], _ENVELOPPES[nom])
    return reste[debut + (1 if nom == "timeout" else 0):]    # `timeout 5 cmd`: la durée est un argument de plus


def _uv(mots: list[Mot], nom: str) -> list[Mot] | None:
    if nom == "uv" and (len(mots) < 2 or mots[1].texte not in ("run", "tool")):
        return None
    reste = mots[1:] if nom == "uvx" else mots[2:]
    if reste and reste[0].texte == "run":
        reste = reste[1:]                                    # `uv tool run`
    return reste[debut_positionnels([m.texte for m in reste], _OPTIONS_UV):]


def _un_cran(mots: list[Mot]) -> list[Mot] | None:
    texte, nom = mots[0].texte, _nom(mots[0].texte)
    if _AFFECTATION.match(texte) or nom in _MOTS_DE_TETE:
        return mots[1:]
    if nom in _ENVELOPPES:
        return _enveloppe(mots, nom)
    return _uv(mots, nom) if nom in ("uv", "uvx") else None


def _deballer(mots: list[Mot]) -> list[Mot]:
    while mots:
        suite = _un_cran(mots)
        if suite is None:
            break
        mots = suite
    return mots


# --- les programmes qui exécutent quelque chose --------------------------------------------------------

def _chaine_c(args: list[str]) -> str | None:
    """La chaîne qui suit `-c` (ou un groupe d'options qui le contient: `-lc`)."""
    for i, a in enumerate(args):
        if a.startswith("-") and not a.startswith("--") and "c" in a[1:]:
            return args[i + 1] if i + 1 < len(args) else ""
    return None


def _ajouter(c: _Ctx, actes_lus: list, distant: bool) -> None:
    """Une commande distante (ssh, docker exec) garde son texte, mais n'écrit rien ici et ne change aucun état local."""
    if distant:
        actes_lus = [replace(a, ecrits=(), partage=False, inoffensif=True, certain=False) for a in actes_lus]
    c.sortie.extend(actes_lus)


def _relire(c: _Ctx, chaine: str, distant: bool = False) -> None:
    _ajouter(c, _analyser(chaine, c.cwd, c.p + 1), distant)


def _direct(c: _Ctx, mots: list[Mot], distant: bool = False) -> None:
    if c.p < PROFONDEUR_MAX and mots:
        lus: list = []
        _commande(mots, c.cwd, c.p + 1, lus, [], [])
        _ajouter(c, lus, distant)


def _x_shell(c: _Ctx) -> None:
    c.brut = True
    chaine = _chaine_c(c.a)
    for source in ([chaine] if chaine is not None else c.corps):
        _relire(c, source)
    c.inoffensif = chaine is not None or bool(c.corps)   # lu: ses actes sont jugés à part; `bash script.sh` ne l'est pas


def _x_su(c: _Ctx) -> None:
    c.brut = True
    chaine = _chaine_c(c.a)
    if chaine is not None:
        _relire(c, chaine)
    c.inoffensif = chaine is not None


def _x_cmd(c: _Ctx) -> None:
    c.brut = True
    a = c.a
    chaine = next((a[i + 1] for i, x in enumerate(a[:-1]) if x.lower() in ("/c", "/k")), None)
    if chaine is not None:
        _relire(c, chaine)


def _x_eval(c: _Ctx) -> None:
    c.brut = True
    _relire(c, " ".join(c.a))


def _x_ssh(c: _Ctx) -> None:
    """ssh relit la commande distante comme un shell: on la relit de même."""
    c.brut = True
    reste = c.a[debut_positionnels(c.a, _SSH_VALEURS) + 1:]
    if reste:
        _relire(c, " ".join(reste), distant=True)


def _x_docker(c: _Ctx) -> None:
    if c.a[:1] != ["exec"]:
        return _x_defaut(c)
    c.brut = True
    sous = c.mots[1:]
    _direct(c, sous[debut_positionnels([m.texte for m in sous], _DOCKER_VALEURS) + 1:], distant=True)


def _x_xargs(c: _Ctx) -> None:
    c.brut = True
    c.inoffensif = True                                     # la commande qu'il lance est jugée à part
    _direct(c, c.mots[debut_positionnels(c.a, _XARGS_VALEURS):])


def _x_find(c: _Ctx) -> None:
    a, i = c.a, 0
    while i < len(a):
        if a[i] in _EXEC_FIND:
            fin = next((j for j in range(i + 1, len(a)) if a[j] in (";", "+")), len(a))
            _direct(c, c.mots[i + 1:fin])
            i = fin
        elif a[i] in _SORTIES_FIND and i + 1 < len(a):
            c.ecrits.append(resoudre(a[i + 1], c.cwd))
        i += 1
    c.lecture = not any(x in a for x in _EXEC_FIND + _SORTIES_FIND + ("-delete",))
    c.inoffensif = "-delete" not in a and not c.ecrits       # `-exec`: la commande lancée est jugée à part


def _codes(prog: str, a: list[str]) -> list[str]:
    if prog in _CODE:
        return valeurs_d_option(a, *_CODE[prog])
    if prog in _CODE_REGEX:
        return [a[i + 1] for i, x in enumerate(a[:-1]) if re.fullmatch(_CODE_REGEX[prog], x)]
    if prog in _POWERSHELL:
        return [a[i + 1] for i, x in enumerate(a[:-1])
                if x.lower() in ("-cwa", "-commandwithargs") or (len(x) >= 2 and "-command".startswith(x.lower()))]
    return positionnels(a, ("-v", "-F", "-f"))[:1]           # awk: le premier argument est le programme


def _fichiers_en_place(prog: str, a: list[str], codes: list[str]) -> list[str]:
    """`perl -pi -e 's/a/b/' f`: avec `-i`, les arguments qui ne sont pas du code sont les fichiers modifiés."""
    en_place = prog in ("perl", "ruby") and any(re.fullmatch(r"-[a-zA-Z]*i[a-zA-Z.]*", x) for x in a)
    return [x for x in positionnels(a) if x not in codes] if en_place else []


def _x_code(c: _Ctx) -> None:
    c.brut = True
    codes = _codes(c.prog, c.a)
    litteraux = [x for code in codes + c.corps for x in chemins_du_code(code, c.prog in _CODE_NUS)]
    c.ecrits += [resoudre(x, c.cwd) for x in litteraux + _fichiers_en_place(c.prog, c.a, codes)]
    c.partage = c.prog == "python" and "--apply" in c.a and any(x.endswith("propagate-methodology.py") for x in c.a)


def _ecrits_git(sous: str, args: list[str]) -> list[str]:
    """Les chemins qu'un geste git écrit: `mv`/`restore`/`rm`, `checkout -- f`, et toute sortie `--output`."""
    sortie = valeurs_d_option(args, (), ("--output",))
    if sous in ("mv", "restore", "rm"):
        sortie += positionnels(args, ("-s", "--source"))
    elif sous == "checkout":
        sortie += _fichiers_du_checkout(args)
    return sortie


def _fichiers_du_checkout(args: list[str]) -> list[str]:
    """`checkout REV -- f`, mais aussi `checkout REV f` ou `checkout f`: tout ce qui suit la révision ressemble à un fichier."""
    if "--" in args:
        return args[args.index("--") + 1:]
    positions = positionnels(args, ("-b", "-B", "--orphan"))
    return positions[1:] + [p for p in positions[:1] if "/" in p or re.search(r"\.\w+$", p)]


def _visible(m: Mot) -> str:
    """Un message (plusieurs mots entre guillemets) devient `Q`; un mot seul (`'init'`, `"compose"`) reste une commande."""
    return "Q" if m.cite and any(ch.isspace() for ch in m.texte) else m.texte


def _x_git(c: _Ctx) -> None:
    sous, reste, cwd = actes_git.lire(c.mots, c.cwd, resoudre)
    args = [m.texte for m in reste]
    c.lecture, c.partage = actes_git.classer(sous, args)
    c.ecrits += [resoudre(x, cwd) for x in _ecrits_git(sous, args)]
    c.dossier = cwd
    c.texte = " ".join(["git", sous] + [_visible(m) for m in reste]).strip()


def _x_defaut(c: _Ctx) -> None:
    c.ecrits += ecrits_du_programme(c.prog, c.a, c.cwd)
    c.lecture = (c.prog in _LECTURES or c.prog in ("sed", "sort") and not c.ecrits) and not (
        c.prog == "rg" and any(x.startswith("--pre") for x in c.a))   # sed/sort: lecture sauf `-i` / `-o` (déjà dans ecrits)
    # `npm version` crée un commit et une étiquette git, sauf avec --no-git-tag-version
    c.partage = c.prog in ("npm", "pnpm", "yarn") and c.a[:1] == ["version"] and "--no-git-tag-version" not in c.a


_EXECUTEURS = {
    **dict.fromkeys(_SHELLS, _x_shell), "su": _x_su, "cmd": _x_cmd, "eval": _x_eval, "ssh": _x_ssh,
    "docker": _x_docker, "xargs": _x_xargs, "find": _x_find, "git": _x_git,
    **dict.fromkeys(list(_CODE) + list(_CODE_REGEX) + list(_POWERSHELL) + list(_AWK), _x_code),
}


# --- l'assemblage --------------------------------------------------------------------------------------

def _cd(c: _Ctx) -> str:
    cible = positionnels(c.a)
    vers = cible[0] if cible else "-"
    c.sortie.append(Acte(c.prog, c.prog, tuple(c.ecrits), lecture=not c.ecrits))
    return "" if vers == "-" or vers.startswith("~") else resoudre(vers, c.cwd)


def _texte(c: _Ctx, programme: str) -> str:
    if c.texte:
        return c.texte
    return " ".join([programme] + [(m.texte if c.brut else _visible(m)) for m in c.mots])


def _commande(mots: list[Mot], cwd: str, p: int, sortie: list, redirs: list, corps: list) -> str:
    """Un segment en mots: ajoute ses actes à `sortie`, rend le dossier courant pour la suite."""
    mots = _deballer(mots)
    ecrits = [resoudre(cible, cwd) for op, cible in redirs if _ecrit_par_redirection(op, cible)]
    if not mots or _nom(mots[0].texte) in _ENTETES:
        sortie += [Acte("", "", tuple(ecrits))] if ecrits else []
        return cwd
    c = _Ctx(_nom(mots[0].texte), mots[1:], cwd, p, sortie, corps, ecrits)
    if c.prog in ("cd", "pushd"):
        return _cd(c)
    _EXECUTEURS.get(c.prog, _x_defaut)(c)
    inoffensif = c.inoffensif or c.lecture or actes_inoffensifs.inoffensif(c.prog, c.a)
    certain = actes_ecrivains.certain(c.prog, c.a)     # fichiers écrits et gestes git: jugés avec la racine
    sortie.append(Acte(c.prog, _texte(c, mots[0].texte), tuple(c.ecrits), c.lecture and not c.ecrits, c.partage,
                       inoffensif and not certain, certain, c.cwd if c.dossier is None else c.dossier))
    return cwd


def _analyser(commande: str, cwd: str = "", p: int = 0) -> list[Acte]:
    if p > PROFONDEUR_MAX:
        return [Acte("?", "?")]
    sortie: list[Acte] = []
    for seg in lire(commande):
        for sous in seg.sous:
            sortie += _analyser(sous, cwd, p + 1)
        cwd = _commande(seg.mots, cwd, p, sortie, seg.redirections, seg.corps)
    return sortie


# --- l'interface ---------------------------------------------------------------------------------------

def actes(commande: str) -> list[Acte]:
    """Les actes d'une commande, imbriqués compris. Une commande illisible est un acte inconnu, jamais une erreur."""
    try:
        return _analyser(commande)
    except Exception:  # un garde-fou ne fait pas tomber une séance sur une commande qu'il ne sait pas lire
        return [Acte("?", "?")]


def chemins_ecrits(commande: str) -> list[str]:
    """Les chemins que la commande écrit, dans l'ordre, sans doublon. Une variable non résolue n'est pas un chemin."""
    return list(dict.fromkeys(e for a in actes(commande) for e in a.ecrits if "$" not in e))


def dans_le_depot(chemin: str, racine: str | None) -> bool:
    """Ce chemin est-il dans le dépôt? Hors du dépôt (`/tmp`, bloc-notes, `~`, `$VAR`, `hote:chemin`, `../voisin`), rien n'est suivi."""
    if racine is None:
        return True
    c = chemin.replace("\\", "/")
    en_git_bash = re.match(r"^/([A-Za-z])/(.*)", c)               # `/d/projet` pour `D:/projet`
    c = f"{en_git_bash.group(1)}:/{en_git_bash.group(2)}" if en_git_bash else c
    if c.startswith("~") or "$" in c or re.match(r"^[^/:]{2,}:", c):
        return False
    c = posixpath.normpath(c)
    if not (c.startswith("/") or re.match(r"^[A-Za-z]:/", c)):
        return c != ".." and not c.startswith("../")                  # relatif au dossier de travail du dépôt
    base = posixpath.normpath(racine.replace("\\", "/")).lower()
    return c.lower() == base or c.lower().startswith(base + "/")


def _ecrit_ici(a: Acte, racine: str | None) -> bool:
    agit_ici = dans_le_depot(a.dossier, racine)
    return ((a.certain or a.partage) and agit_ici) or any(dans_le_depot(e, racine) for e in a.ecrits)


def ecrit(commande: str, racine: str | None = None) -> bool:
    """Écriture CERTAINE: un fichier du dépôt écrit, un geste d'état partagé, un formateur ou gestionnaire connu.

    Seule celle-ci peut faire refuser le commit d'une autre séance (relectures n° 4 à n° 7: une liste d'inoffensifs
    fait refuser à tort, une liste d'écrivains laisse passer; écrire hors du dépôt n'écrit rien de suivi).
    """
    return any(_ecrit_ici(a, racine) for a in actes(commande))


def peut_ecrire(commande: str, racine: str | None = None) -> bool:
    """Écriture certaine OU commande ni lecture ni inoffensive connue (`make`, `./deploy.sh`): avertit seulement."""
    return any(_ecrit_ici(a, racine) or not (a.lecture or a.inoffensif) for a in actes(commande))


def commentaires(commande: str) -> list[str]:
    return shell_lecteur.commentaires(commande)


def est_lecture(commande: str) -> bool:
    """Vrai si chaque acte est une forme de lecture connue (liste fermée): ni écriture, ni exécution de texte."""
    return all(a.lecture and not a.ecrits for a in actes(commande))


def touche_etat_partage(commande: str, racine: str | None = None) -> bool:
    """Le geste change l'historique, la branche ou l'arbre de travail qu'une autre séance utilise (dans CE dépôt)."""
    return any(a.partage and dans_le_depot(a.dossier, racine) for a in actes(commande))


def textes(commande: str) -> list[str]:
    """La forme de chaque acte sur laquelle s'appliquent les motifs de commande (les messages y sont `Q`)."""
    return [a.texte for a in actes(commande)]
