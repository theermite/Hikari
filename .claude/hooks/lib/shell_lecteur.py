"""Lit une commande shell comme le shell: des segments de mots, avec redirections, heredocs, substitutions.

Pourquoi un lecteur de plus (et pas `shell_parse`): il lui faut ce que `shlex` perd. Un mot sait s'il était
entre guillemets (un message de commit n'est pas une commande), les redirections gardent leur cible
(`echo x > f` écrit `f`), les `$( )` et accents graves sont rendus à part (ils s'exécutent), et un heredoc garde
son corps (c'est une donnée, sauf si on le donne à un shell). Un chemin entre guillemets reste UN mot.

Limites écrites: aucune expansion de variable ni de motif; une substitution de processus `<( )` ouvre un
segment sans être suivie; une commande illisible ne lève jamais d'erreur (le texte restant est lu tel quel).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

_ECHAPPABLES = " \t\"'$`;&|<>()#\\"
_OPERATEURS = ("&&", "||", "|&", ";;")
_REDIRECTIONS = ("<<<", "<<-", "<<", ">>", ">&", ">|", "<&")


@dataclass(frozen=True)
class Mot:
    texte: str
    cite: bool = False   # une partie au moins du mot était entre guillemets


@dataclass
class Segment:
    mots: list = field(default_factory=list)
    redirections: list = field(default_factory=list)   # (opérateur, cible)
    corps: list = field(default_factory=list)          # heredocs et here-strings
    sous: list = field(default_factory=list)           # textes de $( ) et ` `


def _fin_guillemets(t: str, i: int) -> int:
    j = i + 1
    while j < len(t) and t[j] != '"':
        j += 2 if t[j] == "\\" else 1
    return min(j, len(t))


def _fin_accent(t: str, i: int) -> int:
    j = i + 1
    while j < len(t) and t[j] != "`":
        j += 2 if t[j] == "\\" else 1
    return min(j, len(t))


def _corps_de(t: str, j: int, delimiteur: str, tabs: bool) -> tuple[str, int]:
    """(corps, index après le délimiteur) d'un heredoc dont le texte commence à `j`."""
    lignes = []
    while j < len(t):
        fin = t.find("\n", j)
        fin = len(t) if fin < 0 else fin
        ligne = t[j:fin].rstrip("\r")
        j = min(fin + 1, len(t))
        if (ligne.lstrip("\t") if tabs else ligne) == delimiteur:
            break
        lignes.append(ligne)
    return "\n".join(lignes), j


def _annonce_corps(t: str, j: int, attendus: list) -> int:
    m = re.match(r"<<(-?)\s*(['\"]?)(\w+)\2", t[j:])
    if not m:
        return j + 2
    attendus.append((m.group(3), bool(m.group(1))))
    return j + m.end()


def _sauter(t: str, j: int, attendus: list) -> int | None:
    """Saute ce qui est inerte pour compter les parenthèses (guillemets, échappement, heredoc); None sinon."""
    c = t[j]
    if c == "\\":
        return j + 2
    if c == "'":
        k = t.find("'", j + 1)
        return len(t) if k < 0 else k + 1
    if c == '"':
        return _fin_guillemets(t, j) + 1
    if c == "\n" and attendus:
        for delimiteur, tabs in attendus:
            j = _corps_de(t, j + 1, delimiteur, tabs)[1]
        attendus.clear()
        return j
    if t.startswith("<<", j) and not t.startswith("<<<", j):
        return _annonce_corps(t, j, attendus)
    return None


def _fin_parenthese(t: str, i: int) -> int:
    """Index de la `)` qui ferme la `(` de t[i] (len(t) si elle ne se ferme pas)."""
    profondeur, j, attendus = 0, i, []
    while j < len(t):
        saut = _sauter(t, j, attendus)
        if saut is not None:
            j = saut
            continue
        profondeur += (t[j] == "(") - (t[j] == ")")
        if profondeur == 0:
            return j
        j += 1
    return len(t)


class _Lecteur:
    def __init__(self, texte: str):
        self.t, self.i = texte, 0
        self.segments: list[Segment] = []
        self.seg = Segment()
        self.buf: list[str] = []
        self.mot = self.cite = False
        self.attente: str | None = None            # redirection qui attend sa cible
        self.corps_attendus: list = []             # (délimiteur, tabulations, segment)
        self.commentaires: list[str] = []          # `# …` hors guillemets, au niveau principal
        self.gestes = {
            "\n": self._saut, " ": self._espace, "\t": self._espace, "\r": self._espace, "\\": self._echappe,
            "#": self._commentaire, "'": self._simple, '"': self._double, "`": self._accent, "$": self._dollar,
            "<": self._redirection, ">": self._redirection, "&": self._esperluette,
            ";": self._separateur, "|": self._separateur, "(": self._separateur, ")": self._separateur,
        }

    def lire(self) -> list[Segment]:
        while self.i < len(self.t):
            self.gestes.get(self.t[self.i], self._caractere)()
        self._fin_segment()
        return self.segments

    # -- mots et segments
    def _ajoute(self, texte: str, cite: bool = False) -> None:
        self.buf.append(texte)
        self.mot = True
        self.cite = self.cite or cite

    def _fin_mot(self) -> None:
        if not self.mot:
            return
        m = Mot("".join(self.buf), self.cite)
        self.buf, self.mot, self.cite = [], False, False
        op, self.attente = self.attente, None
        if op is None:
            self.seg.mots.append(m)
        elif op in ("<<", "<<-"):
            self.corps_attendus.append((m.texte, op == "<<-", self.seg))
        elif op == "<<<":
            self.seg.corps.append(m.texte)
        else:
            self.seg.redirections.append((op, m.texte))

    def _fin_segment(self) -> None:
        self._fin_mot()
        self.attente = None
        s = self.seg
        if s.mots or s.redirections or s.corps or s.sous or any(x is s for _, _, x in self.corps_attendus):
            self.segments.append(s)
        self.seg = Segment()

    # -- gestes, un par caractère significatif
    def _caractere(self) -> None:
        self._ajoute(self.t[self.i])
        self.i += 1

    def _espace(self) -> None:
        self._fin_mot()
        self.i += 1

    def _saut(self) -> None:
        self._fin_segment()
        self.i += 1
        for delimiteur, tabs, seg in self.corps_attendus:
            corps, self.i = _corps_de(self.t, self.i, delimiteur, tabs)
            seg.corps.append(corps)
        self.corps_attendus = []

    def _commentaire(self) -> None:
        if self.mot:
            return self._caractere()
        fin = self.t.find("\n", self.i)
        fin = len(self.t) if fin < 0 else fin
        self.commentaires.append(self.t[self.i:fin].rstrip())
        self.i = fin

    def _simple(self) -> None:
        fin = self.t.find("'", self.i + 1)
        fin = len(self.t) if fin < 0 else fin
        self._ajoute(self.t[self.i + 1:fin], cite=True)
        self.i = fin + 1

    def _substitution(self, debut: int, fin: int, ouverture: int) -> int:
        self.seg.sous.append(self.t[debut + ouverture:fin])
        self._ajoute("$()")
        return fin + 1

    def _accent(self) -> None:
        self.i = self._substitution(self.i, _fin_accent(self.t, self.i), 1)

    def _dollar(self) -> None:
        if not self.t.startswith("$(", self.i):
            return self._caractere()
        self.i = self._substitution(self.i, _fin_parenthese(self.t, self.i + 1), 2)

    def _echappe(self) -> None:
        suivant = self.t[self.i + 1] if self.i + 1 < len(self.t) else ""
        if suivant == "\n":
            self.i += 2
        elif suivant and suivant in _ECHAPPABLES:
            self._ajoute(suivant)
            self.i += 2
        else:
            self._ajoute("\\")                     # `D:\x\y`: la barre oblique d'un chemin reste telle quelle
            self.i += 1

    def _double(self) -> None:
        self._ajoute("", cite=True)
        j = self.i + 1
        while j < len(self.t) and self.t[j] != '"':
            j = self._pas_double(j)
        self.i = j + 1

    def _pas_double(self, j: int) -> int:
        t, c = self.t, self.t[j]
        if c == "\\" and j + 1 < len(t):
            if t[j + 1] in '"\\$`':
                self.buf.append(t[j + 1])
            elif t[j + 1] != "\n":
                self.buf.append("\\" + t[j + 1])
            return j + 2
        if c == "$" and t.startswith("$(", j):
            return self._substitution(j, _fin_parenthese(t, j + 1), 2)
        if c == "`":
            return self._substitution(j, _fin_accent(t, j), 1)
        self.buf.append(c)
        return j + 1

    def _redirection(self) -> None:
        if self.mot and not self.cite and "".join(self.buf).isdigit():
            self.buf, self.mot = [], False        # `2>`: le chiffre est un descripteur, pas un mot
        else:
            self._fin_mot()
        op = next((o for o in _REDIRECTIONS if self.t.startswith(o, self.i)), self.t[self.i])
        self.i += len(op)
        if op in ("<", ">") and self.t.startswith("(", self.i):
            return                                 # substitution de processus: la parenthèse ouvre un segment
        self.attente = op

    def _esperluette(self) -> None:
        if not self.t.startswith("&>", self.i):
            return self._separateur()
        self._fin_mot()
        op = "&>>" if self.t.startswith("&>>", self.i) else "&>"
        self.i += len(op)
        self.attente = op

    def _separateur(self) -> None:
        op = next((o for o in _OPERATEURS if self.t.startswith(o, self.i)), self.t[self.i])
        self._fin_segment()
        self.i += len(op)


def lire(texte: str) -> list[Segment]:
    return _Lecteur(texte).lire()


def commentaires(texte: str) -> list[str]:
    """Les vrais commentaires de la commande: ce qui suit un `#` hors guillemets, jamais le texte d'un message."""
    lecteur = _Lecteur(texte)
    lecteur.lire()
    return lecteur.commentaires
