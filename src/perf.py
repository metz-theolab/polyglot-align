"""Mesure des performances d'une expérience : durée, temps CPU, mémoire, débit.

Experiment chronomètre chaque phase séparément :
    chargement    construction de l'aligneur (chargement, voire téléchargement, du modèle)
    apprentissage Aligner.fit (eflomal ; quasi nul pour SimAlign et le LLM)
    alignement    Aligner.align sur tous les versets des passages
    evaluation    jugement des liens et CSV de relecture (identique pour tous les aligneurs)

et écrit results/<nom>/perf.json. Pour comparer des méthodes, retenir
« apprentissage + alignement » (`cout_methode`) ; le chargement dépend du cache
et du réseau, l'évaluation ne dépend pas de l'aligneur.

Temps CPU = utilisateur + système, tous les fils d'exécution confondus : il peut
dépasser la durée réelle quand torch calcule sur plusieurs cœurs (`cpu / duree`
≈ nombre de cœurs occupés en moyenne).

Limites :
- le LLM tourne dans un autre processus (serveur Ollama) : son CPU et sa mémoire
  n'apparaissent pas ici ; les comptes de tokens d'Ollama sont dans `aligneur` ;
- une durée n'est comparable qu'entre expériences lancées sur la même machine
  (décrite dans `machine`).
"""
import json
import os
import platform
import resource
import subprocess
import sys
import time
from contextlib import contextmanager
from datetime import datetime
from importlib import metadata

PACKAGES = ["torch", "transformers", "simalign", "eflomal"]


def cpu_seconds() -> float:
    """Temps CPU (utilisateur + système) du processus et de ses enfants terminés."""
    total = 0.0
    for who in (resource.RUSAGE_SELF, resource.RUSAGE_CHILDREN):
        r = resource.getrusage(who)
        total += r.ru_utime + r.ru_stime
    return total


def peak_memory_mb() -> float:
    """Mémoire résidente maximale du processus depuis son lancement, en Mo
    (ru_maxrss est en octets sous macOS, en kilo-octets sous Linux)."""
    rss = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    return rss / 2**20 if sys.platform == "darwin" else rss / 2**10


def cpu_name() -> str:
    try:
        if sys.platform == "darwin":
            return subprocess.run(["sysctl", "-n", "machdep.cpu.brand_string"],
                                  capture_output=True, text=True).stdout.strip()
        with open("/proc/cpuinfo") as f:
            for line in f:
                if line.startswith("model name"):
                    return line.split(":", 1)[1].strip()
    except OSError:
        pass
    return platform.processor()


def machine(device: str | None) -> dict:
    """Description de la machine et des versions, pour que les durées aient un sens."""
    versions = {}
    for p in PACKAGES:
        try:
            versions[p] = metadata.version(p)
        except metadata.PackageNotFoundError:
            pass
    return {"systeme": platform.platform(), "processeur": cpu_name(),
            "coeurs": os.cpu_count(), "python": platform.python_version(),
            "device": device, "versions": versions}


class PerfMeter:
    """Chronomètre les phases d'une expérience (with meter.phase("alignement"): ...)."""

    def __init__(self):
        self.phases = {}        # nom -> {"duree_s", "cpu_s"}, cumulés si la phase revient
        self.start = datetime.now().isoformat(timespec="seconds")

    @contextmanager
    def phase(self, name: str):
        t0, c0 = time.perf_counter(), cpu_seconds()
        try:
            yield
        finally:
            p = self.phases.setdefault(name, {"duree_s": 0.0, "cpu_s": 0.0})
            p["duree_s"] += time.perf_counter() - t0
            p["cpu_s"] += cpu_seconds() - c0

    def report(self, versets: int, tokens_hb: int, tokens_gr: int,
               device: str | None = None, aligner_stats: dict | None = None) -> dict:
        """Le contenu de perf.json."""
        get = lambda name, key: self.phases.get(name, {}).get(key, 0.0)
        cost = get("apprentissage", "duree_s") + get("alignement", "duree_s")
        cost_cpu = get("apprentissage", "cpu_s") + get("alignement", "cpu_s")
        align_s = get("alignement", "duree_s")
        tokens = tokens_hb + tokens_gr
        rate = lambda n, s: round(n / s, 2) if s > 0 else None
        aligner_stats = dict(aligner_stats or {})
        if aligner_stats.get("ollama_eval_duration"):   # LLM : débit de génération du serveur
            aligner_stats["ollama_tokens_generes_par_s"] = rate(
                aligner_stats["ollama_eval_count"], aligner_stats["ollama_eval_duration"] / 1e9)
        return {
            "debut": self.start,
            "phases": {n: {k: round(v, 3) for k, v in p.items()} for n, p in self.phases.items()},
            "total": {"duree_s": round(sum(p["duree_s"] for p in self.phases.values()), 3),
                      "cpu_s": round(sum(p["cpu_s"] for p in self.phases.values()), 3)},
            "cout_methode": {"duree_s": round(cost, 3), "cpu_s": round(cost_cpu, 3),
                             "s_par_1000_versets": round(1000 * cost / versets, 3) if versets else None},
            "debit_alignement": {"versets_par_s": rate(versets, align_s),
                                 "tokens_par_s": rate(tokens, align_s)},
            "volume": {"versets": versets, "tokens_hb": tokens_hb, "tokens_gr": tokens_gr},
            "memoire_max_mo": round(peak_memory_mb(), 1),
            "machine": machine(device),
            "aligneur": aligner_stats,
        }
