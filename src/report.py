"""Rapport : tableaux et figures pour l'article, à partir des résultats existants.

Voir DECISIONS.md « Module de rapport ». Ne lance aucun alignement : lit
results/<nom>/scores.json et la copie results/<nom>/config.yaml.

Usage (depuis la racine du projet) :
    python src/report.py reports/article.yaml   ->  reports/article/

Garde-fous :
- libellés tirés de la copie de la config (results/<nom>/config.yaml), avec un
  avertissement si elle diffère de experiments/<nom>.yaml ;
- exécutions multiples <nom>_run1, <nom>_run2… regroupées : moyenne ± écart-type ;
- mesures recalculées en micro à partir des comptes (evaluate.measures),
  jamais par moyenne de pourcentages ;
- avertissement si les expériences d'un tableau n'ont pas été évaluées sur les
  mêmes versets.
"""
import csv
import json
import re
import statistics
import sys
import unicodedata
from collections import Counter
from pathlib import Path

import yaml

from config import Config
from evaluate import measures

# libellés des colonnes (mesures de evaluate.measures)
COLUMN_LABELS = {
    "precision": "Précision", "rappel_blocs": "Rappel (blocs)", "f1": "F1",
    "nonalign_exactitude": "Non-alignements", "aer": "AER",
    "aer_precision": "Précision (AER)", "aer_rappel": "Rappel (AER)",
    "couverture_hb": "Couverture hébreu", "couverture_gr": "Couverture grec",
}
DEFAULT_COLUMNS = ["precision", "rappel_blocs", "f1", "nonalign_exactitude"]

MODEL_LABELS = {"bert": "mBERT", "xlmr": "XLM-R", "cis-lmu/glot500-base": "Glot500"}

# couleur fixe par famille d'aligneur (la couleur suit l'aligneur, pas son rang) ;
# palette catégorielle validée (dataviz, references/palette.md), ordre fixe
SERIES = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300"]
FAMILY_SLOT = {"mBERT": 0, "XLM-R": 1, "Glot500": 2, "eflomal": 3, "LLM": 4}
INK, INK_MUTED, GRID = "#1f1f1e", "#6b6a64", "#e4e3dd"


def slug(text: str) -> str:
    """« Comparaison des aligneurs » -> comparaison_des_aligneurs."""
    text = unicodedata.normalize("NFD", text.lower())
    text = "".join(c for c in text if not unicodedata.combining(c))
    return re.sub(r"[^a-z0-9]+", "_", text).strip("_")


def yaml_data(path: Path) -> dict:
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


# --- résultats ---

class ExperimentResult:
    """Une expérience terminée : results/<nom>/ (scores.json, config.yaml)."""

    def __init__(self, name: str, results_root="results", experiments_root="experiments"):
        self.name = name
        self.dir = Path(results_root) / name
        if not (self.dir / "scores.json").exists():
            raise FileNotFoundError(f"{self.dir}/scores.json absent : lancer d'abord l'expérience")
        self.scores = json.loads((self.dir / "scores.json").read_text(encoding="utf-8"))
        raw = yaml_data(self.dir / "config.yaml")
        # options absentes des anciennes configs : valeurs par défaut de Config
        self.config = {f: getattr(Config, f) for f in Config.__dataclass_fields__
                       if hasattr(Config, f)} | raw
        self._raw_config = raw
        self.warnings = []
        self._check_config(Path(experiments_root))

    def _check_config(self, experiments_root: Path) -> None:
        """La copie de la config doit correspondre au YAML de l'expérience."""
        base = re.sub(r"_run\d+$", "", self.name)
        source = experiments_root / f"{base}.yaml"
        if not source.exists():
            return
        defaults = {f: getattr(Config, f) for f in Config.__dataclass_fields__ if hasattr(Config, f)}
        current = defaults | yaml_data(source)
        diff = sorted(k for k in set(current) | set(self.config)
                      if k != "name" and current.get(k) != self.config.get(k))
        if diff:
            self.warnings.append(f"{self.name} : config des résultats ≠ {source} ({', '.join(diff)}) ; "
                                 "libellés tirés des résultats")

    @property
    def passages(self) -> list:
        return [p for p in self.scores if p != "TOTAL"]

    @property
    def methods(self) -> list:
        return list(self.scores["TOTAL"]["methodes"])

    def counts(self, method: str, passages=None) -> Counter:
        """Somme des comptes bruts de `method` sur `passages` (tous par défaut)."""
        if method not in self.methods:
            raise KeyError(f"{self.name} : méthode {method!r} absente (méthodes : {', '.join(self.methods)})")
        total = Counter()
        for p in passages or self.passages:
            if p not in self.scores:
                raise KeyError(f"{self.name} : passage {p!r} absent (passages : {', '.join(self.passages)})")
            total.update(self.scores[p]["methodes"][method]["comptes"])
        return total

    def family(self) -> str:
        """mBERT, XLM-R, Glot500, eflomal, LLM : famille d'aligneur (couleur des figures)."""
        aligner = self.config.get("aligner", "simalign")
        if aligner == "llm":
            return "LLM"
        if aligner == "eflomal":
            return "eflomal"
        model = self.config.get("model", "bert")
        return MODEL_LABELS.get(model, model)

    def label(self, keys=None) -> str:
        """Libellé lu dans la config : `keys` donnés (rows_from), sinon description
        automatique (aligneur, segmentation, vocalisation)."""
        c = self.config
        if keys:
            return ", ".join(f"{k} = {c.get(k)}" for k in keys)
        parts = [self.family() if c.get("aligner") != "llm" else (c.get("llm_model") or "LLM")]
        parts.append({"w": "mots BHSA", "g": "mots graphiques", "l": "lemmes"}[c.get("tokens", "w")])
        if c.get("hebrew_vocalization"):
            parts.append("voyelles")
        return " · ".join(parts)


class ResultGroup:
    """Une expérience et ses exécutions répétées (<nom>_run1, <nom>_run2…)."""

    def __init__(self, name: str, results_root="results", experiments_root="experiments"):
        root = Path(results_root)
        runs = sorted((p.name for p in root.glob(f"{name}_run*") if re.fullmatch(rf"{re.escape(name)}_run\d+", p.name)),
                      key=lambda n: int(n.rsplit("run", 1)[1]))
        names = runs or [name]
        self.name = name
        self.runs = [ExperimentResult(n, results_root, experiments_root) for n in names]
        self.first = self.runs[0]

    @property
    def warnings(self) -> list:
        return [w for r in self.runs for w in r.warnings]

    def resolve_method(self, method=None) -> str:
        """Méthode demandée ; si elle n'existe pas et que l'expérience n'en a
        qu'une (LLM), on prend celle-là."""
        available = self.first.methods
        if method in available:
            return method
        if len(available) == 1:
            return available[0]
        raise KeyError(f"{self.name} : méthode {method!r} absente (méthodes : {', '.join(available)})")

    def measures(self, method: str, passages=None) -> dict:
        """{mesure: (moyenne, écart-type ou None)} ; écart-type si plusieurs exécutions."""
        per_run = [measures(r.counts(method, passages)) for r in self.runs]
        out = {}
        for k in per_run[0]:
            values = [m[k] for m in per_run if m[k] is not None]
            if not values:
                out[k] = (None, None)
            else:
                out[k] = (statistics.mean(values), statistics.stdev(values) if len(values) > 1 else None)
        return out

    def verses(self, method: str, passages=None) -> int:
        return self.first.counts(method, passages)["versets"]


# --- tableaux ---

class Table:
    """Un tableau du rapport, décrit dans le YAML :
        title: ...
        experiments: [nom, {name: nom, method: llm, label: ...}, ...]
        method: inter                # par défaut pour toutes les expériences
        columns: [precision, ...]
        rows_from: [tokens, ...]     # libellés lus dans config.yaml
        passages: [Gen.3]            # restreindre aux passages communs (défaut : tous)
    ou, pour une seule expérience, une ligne par passage (ex. par livre) :
        title: ...
        experiment: eflomal_formes_bible
        rows: passages
    """

    def __init__(self, spec: dict, results_root="results", experiments_root="experiments"):
        self.spec = spec
        self.title = spec["title"]
        self.columns = spec.get("columns", DEFAULT_COLUMNS)
        unknown = set(self.columns) - set(COLUMN_LABELS)
        if unknown:
            raise ValueError(f"tableau « {self.title} » : colonne(s) inconnue(s) {', '.join(sorted(unknown))}")
        self.roots = (results_root, experiments_root)
        self.rows = []          # (libellé, {colonne: (moyenne, écart)}, nombre de versets)
        self.warnings = []
        self.multi_run = False

    def build(self) -> "Table":
        if self.spec.get("rows") == "passages":
            self._build_by_passage()
        else:
            self._build_by_experiment()
        return self

    def _build_by_experiment(self) -> None:
        passages = self.spec.get("passages")
        verse_counts = {}
        for item in self.spec["experiments"]:
            item = item if isinstance(item, dict) else {"name": item}
            group = ResultGroup(item["name"], *self.roots)
            self.warnings += group.warnings
            method = group.resolve_method(item.get("method", self.spec.get("method", "inter")))
            label = item.get("label") or group.first.label(self.spec.get("rows_from"))
            if method != self.spec.get("method", "inter"):
                label += f" ({method})"
            m = group.measures(method, passages)
            n = group.verses(method, passages)
            verse_counts[label] = n
            self.multi_run |= len(group.runs) > 1
            self.rows.append((label, {c: m[c] for c in self.columns}, n))
        if len(set(verse_counts.values())) > 1:
            detail = ", ".join(f"{k} : {v}" for k, v in verse_counts.items())
            self.warnings.append(f"« {self.title} » : expériences évaluées sur des nombres de versets "
                                 f"différents ({detail}) ; restreindre avec `passages:`")

    def _build_by_passage(self) -> None:
        group = ResultGroup(self.spec["experiment"], *self.roots)
        self.warnings += group.warnings
        method = group.resolve_method(self.spec.get("method", "inter"))
        self.multi_run = len(group.runs) > 1
        for p in group.first.passages + ["TOTAL"]:
            passages = None if p == "TOTAL" else [p]
            m = group.measures(method, passages)
            self.rows.append((p, {c: m[c] for c in self.columns}, group.verses(method, passages)))

    # --- écriture ---

    @staticmethod
    def fmt(value, std=None, percent_sign="%") -> str:
        if value is None:
            return "—"
        text = f"{value * 100:.1f}"
        if std is not None:
            text += f" ± {std * 100:.1f}"
        return text + percent_sign

    def header(self) -> list:
        first = "Livre" if self.spec.get("rows") == "passages" else "Expérience"
        return [first] + [COLUMN_LABELS[c] for c in self.columns] + ["Versets"]

    def to_csv(self, path: Path) -> None:
        with open(path, "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(["ligne"] + [x for c in self.columns for x in (c, f"{c}_ecart")] + ["versets"])
            for label, vals, n in self.rows:
                w.writerow([label] + [x for c in self.columns for x in vals[c]] + [n])

    def to_md(self, path: Path) -> None:
        lines = [f"**{self.title}**", "", "| " + " | ".join(self.header()) + " |",
                 "|" + "---|" + "---:|" * (len(self.columns) + 1)]
        for label, vals, n in self.rows:
            lines.append("| " + " | ".join([label] + [self.fmt(*vals[c]) for c in self.columns] + [str(n)]) + " |")
        if self.multi_run:
            lines += ["", "Moyenne ± écart-type sur les exécutions répétées."]
        path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    def to_tex(self, path: Path) -> None:
        esc = lambda s: re.sub(r"([_&%#$])", r"\\\1", str(s))
        lines = [r"\begin{table}[ht]", r"\centering", f"\\caption{{{esc(self.title)}}}",
                 f"\\label{{tab:{slug(self.title)}}}",
                 r"\begin{tabular}{l" + "r" * (len(self.columns) + 1) + "}", r"\toprule",
                 " & ".join(esc(h) for h in self.header()) + r" \\", r"\midrule"]
        for label, vals, n in self.rows:
            if label == "TOTAL":
                lines.append(r"\midrule")
            cells = [esc(label)] + [self.fmt(*vals[c], percent_sign="").replace("±", r"$\pm$")
                                    for c in self.columns] + [str(n)]
            lines.append(" & ".join(cells) + r" \\")
        lines += [r"\bottomrule", r"\end{tabular}"]
        if self.multi_run:
            lines.append(r"\\[2pt]{\footnotesize Moyenne $\pm$ écart-type sur les exécutions répétées.}")
        lines.append(r"\end{table}")
        path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    def write(self, out_dir: Path) -> None:
        stem = out_dir / slug(self.title)
        self.to_tex(stem.with_suffix(".tex"))
        self.to_md(stem.with_suffix(".md"))
        self.to_csv(stem.with_suffix(".csv"))


# --- figures ---

class Figures:
    """Figures matplotlib, en .pdf (article) et .png (slides).
    precision_rappel : un point par expérience ;
    par_livre        : précision et rappel par livre d'une expérience."""

    def __init__(self, out_dir: Path, results_root="results", experiments_root="experiments"):
        self.out = out_dir
        self.roots = (results_root, experiments_root)
        self.warnings = []
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        self.plt = plt
        plt.rcParams.update({
            "font.size": 9, "axes.edgecolor": INK_MUTED, "axes.labelcolor": INK,
            "xtick.color": INK_MUTED, "ytick.color": INK_MUTED, "text.color": INK,
            "axes.spines.top": False, "axes.spines.right": False,
            "axes.grid": True, "grid.color": GRID, "grid.linewidth": 0.6,
            "axes.axisbelow": True, "legend.frameon": False,
        })

    def save(self, fig, name: str) -> None:
        fig.savefig(self.out / f"{name}.pdf", bbox_inches="tight")
        fig.savefig(self.out / f"{name}.png", dpi=200, bbox_inches="tight")
        self.plt.close(fig)

    def precision_rappel(self, spec: dict) -> None:
        """Précision × rappel par blocs, un point par expérience, couleur par famille."""
        fig, ax = self.plt.subplots(figsize=(5.2, 4))
        seen, points = set(), []
        for item in spec["experiments"]:
            item = item if isinstance(item, dict) else {"name": item}
            group = ResultGroup(item["name"], *self.roots)
            self.warnings += group.warnings
            method = group.resolve_method(item.get("method", spec.get("method", "inter")))
            m = group.measures(method, spec.get("passages"))
            family = group.first.family()
            color = SERIES[FAMILY_SLOT.get(family, len(FAMILY_SLOT)) % len(SERIES)]
            (p, p_sd), (r, r_sd) = m["precision"], m["rappel_blocs"]
            ax.errorbar(r, p, xerr=r_sd, yerr=p_sd, fmt="o", ms=8, color=color, mec="white", mew=2,
                        ecolor=color, elinewidth=1, label=family if family not in seen else None,
                        zorder=3)
            seen.add(family)
            label = item.get("label") or group.first.label()
            if method != spec.get("method", "inter"):
                label += f" ({method})"
            points.append((r, p, label))
        ax.margins(0.08)
        ax.set_xlabel("Rappel par blocs")
        ax.set_ylabel("Précision")
        ax.xaxis.set_major_formatter(self.plt.FuncFormatter(lambda v, _: f"{v:.0%}"))
        ax.yaxis.set_major_formatter(self.plt.FuncFormatter(lambda v, _: f"{v:.0%}"))
        self._label_points(fig, ax, points)
        # légende sous le graphique : ne masque aucun point
        ax.legend(loc="upper center", bbox_to_anchor=(0.5, -0.14), ncol=len(seen), fontsize=8,
                  handletextpad=0.3, columnspacing=1.2)
        ax.set_title(spec.get("title", "Précision et rappel par blocs"), loc="left", fontsize=10)
        self.save(fig, spec.get("file", "precision_rappel"))

    def _label_points(self, fig, ax, points, line=10) -> None:
        """Étiquettes directes sans chevauchement : à droite du point, ou à gauche
        dans le tiers droit du graphique ; une étiquette qui en recouvrirait une
        autre du même côté est décalée vers le bas, ligne par ligne (en points)."""
        fig.canvas.draw()
        to_pt = 72 / fig.dpi
        x0, x1 = ax.get_xlim()
        placed = []            # (côté, x en points, y en points) des étiquettes posées
        for r, p, label in sorted(points, key=lambda t: -t[1]):
            side = "left" if (r - x0) / (x1 - x0) > 0.66 else "right"
            px, py = (v * to_pt for v in ax.transData.transform((r, p)))
            dy = 0
            while any(s == side and abs(x - px) < 140 and abs(y - (py + dy)) < line
                      for s, x, y in placed):
                dy -= line
            placed.append((side, px, py + dy))
            ax.annotate(label, (r, p), xytext=(-8 if side == "left" else 8, dy),
                        textcoords="offset points", ha="right" if side == "left" else "left",
                        va="center", fontsize=7, color=INK_MUTED)

    def par_livre(self, spec: dict) -> None:
        """Précision et rappel par livre (diagramme en points), livres triés par F1."""
        group = ResultGroup(spec["experiment"], *self.roots)
        self.warnings += group.warnings
        method = group.resolve_method(spec.get("method", "inter"))
        rows = []
        for book in group.first.passages:
            m = group.measures(method, [book])
            rows.append((book, m["precision"][0], m["rappel_blocs"][0], m["f1"][0] or 0))
        rows.sort(key=lambda r: r[3])
        fig, ax = self.plt.subplots(figsize=(5.2, 0.17 * len(rows) + 0.9))
        y = range(len(rows))
        ax.hlines(y, [min(r[1], r[2]) for r in rows], [max(r[1], r[2]) for r in rows],
                  color=GRID, linewidth=2)
        ax.plot([r[1] for r in rows], y, "o", ms=5, color=SERIES[0], label="Précision")
        ax.plot([r[2] for r in rows], y, "o", ms=5, color=SERIES[1], label="Rappel par blocs")
        ax.set_yticks(list(y), [r[0] for r in rows], fontsize=7)
        ax.grid(axis="y", visible=False)
        ax.xaxis.set_major_formatter(self.plt.FuncFormatter(lambda v, _: f"{v:.0%}"))
        ax.legend(loc="lower right", fontsize=8)
        title = spec.get("title", f"Par livre — {group.first.label()} ({method})")
        ax.set_title(title, loc="left", fontsize=10)
        self.save(fig, spec.get("file", "par_livre"))


# --- rapport ---

class Report:
    def __init__(self, spec: dict, out_root="reports", results_root="results",
                 experiments_root="experiments"):
        self.spec = spec
        self.name = spec["name"]
        self.out = Path(out_root) / self.name
        self.roots = (results_root, experiments_root)
        self.warnings = []

    @classmethod
    def from_yaml(cls, path, **kwargs) -> "Report":
        return cls(yaml_data(Path(path)), **kwargs)

    def run(self) -> None:
        (self.out / "tables").mkdir(parents=True, exist_ok=True)
        tables = [Table(t, *self.roots).build() for t in self.spec.get("tables", [])]
        for t in tables:
            t.write(self.out / "tables")
            self.warnings += t.warnings
            print(f"tableau : {self.out}/tables/{slug(t.title)}.(tex|md|csv)")
        self.figures(tables)
        for w in dict.fromkeys(self.warnings):
            print(f"ATTENTION : {w}")

    def figures(self, tables) -> None:
        specs = self.spec.get("figures", [])
        if not specs:
            return
        (self.out / "figures").mkdir(parents=True, exist_ok=True)
        try:
            figs = Figures(self.out / "figures", *self.roots)
        except ImportError:
            print("matplotlib absent (pip install -r requirements.txt) : figures non produites")
            return
        default_experiments = list(dict.fromkeys(
            e for t in self.spec.get("tables", []) for e in t.get("experiments", [])
            if not isinstance(e, dict))) if tables else []
        for spec in specs:
            spec = spec if isinstance(spec, dict) else {"figure": spec}
            kind = spec["figure"]
            if kind == "precision_rappel":
                spec.setdefault("experiments", default_experiments)
            elif kind == "par_livre" and "experiment" not in spec:
                raise ValueError("figure par_livre : donner `experiment:` (une expérience par livre)")
            if not hasattr(figs, kind) or kind.startswith("_"):
                raise ValueError(f"figure inconnue : {kind} (precision_rappel, par_livre)")
            getattr(figs, kind)(spec)
            print(f"figure : {self.out}/figures/{spec.get('file', kind)}.(pdf|png)")
        self.warnings += figs.warnings


if __name__ == "__main__":
    Report.from_yaml(sys.argv[1] if len(sys.argv) > 1 else "reports/article.yaml").run()
