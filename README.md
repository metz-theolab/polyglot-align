# 📜 polyglot-align --- Multilingual word alignments : Ancient Hebrew and its Greek translations

**polyglot-align** is a Python package for automatic word-by-word alignment
of the Hebrew text of the Bible (BHSA) with its Greek translation, the
Septuagint (Rahlfs). Alignments are evaluated against the manual CATSS
alignment.

The package offers a common interface to several alignment methods:

* **SimAlign**: alignment from multilingual embeddings (mBERT, XLM-R,
  Glot500), see [SimAlign](https://github.com/cisnlp/simalign);
* **eflomal**: statistical aligner, trained on the whole corpus, see
  [eflomal](https://github.com/robertostling/eflomal);
* **local LLM**: a model served by [Ollama](https://ollama.com) (e.g.
  Gemma 4 12B) aligns the verse as a table.

---

## 🛠️ Installation

Python 3.10 or later (tested with 3.13). From the root of the repository:

```bash
python -m venv venv
source venv/bin/activate
pip install -e . # '.[all]'
```
<!--
`[all]` installs everything. You can install only what you need:

| Extra | Contents |
|---|---|
| `simalign` | SimAlign, with torch, transformers and the tokenizer dependencies of Glot500 (`sentencepiece`, `tiktoken`, `protobuf`) |
| `eflomal` | eflomal (C extension, compiled at install time) |
| `report` | matplotlib, for the figures of the report |
| `export` | Text-Fabric, to regenerate the texts in `data/` |
| `dev` | flake8 |

Example: `pip install -e '.[eflomal,report]'`. Minimum versions are in
`pyproject.toml`. -->

Hugging Face models (mBERT, XLM-R, Glot500) are downloaded on first use. For
the LLM aligner: install [Ollama](https://ollama.com), then a model
(`ollama pull gemma4:12b`); no Python package is needed.

<details>
<summary><b>eflomal on macOS</b> (error <code>-fopenmp</code> or <code>library 'gomp' not found</code>)</summary>

eflomal is compiled with OpenMP, which Apple's clang does not support, and
its Makefile asks for the GNU `gomp` library. Compile with Homebrew's clang
and make `libomp` stand in for `gomp` during compilation:

```bash
brew install llvm libomp
export CC="$(brew --prefix llvm)/bin/clang"
mkdir -p /tmp/gomp && ln -sf "$(brew --prefix libomp)/lib/libomp.dylib" /tmp/gomp/libgomp.dylib
export LIBRARY_PATH=/tmp/gomp
pip install --no-cache-dir eflomal
```

The compiled program then uses `libomp` directly; `/tmp/gomp` can be
deleted.
</details>

---

## 🚀 Usage

### 1️⃣ Command line

An experiment is described by a YAML file in `experiments/`:

```yaml
name: glot500_vocalized        # results folder: results/<name>/

passages:                      # Hebrew book; Greek book if different; chapter or verse
  - {book: Gen}                # whole book
  - {book: Gen, only: Gen.3}   # one chapter
  - {book: Judg, lxx_book: JudgA}   # Rahlfs' double texts

# text given to the aligner (options understood by every aligner)
tokens: w            # w = BHSA words (בְּ רֵאשִׁית), g = graphic words (בְּרֵאשִׁית), l = lemmas
hebrew: vocalized    # pointed (vowels and teamim), vocalized, unvocalized
greek: unaccented    # accented, unaccented = accents and breathings removed, lowercase

aligner:             # method and its own options
  type: eflomal      # no option of its own; symmetrizations inter and gdfa
```

Options of the other aligners:

```yaml
aligner:             # method and its own options
  type: simalign     # simalign | eflomal | llm
  model: cis-lmu/glot500-base   # bert (mBERT), xlmr, or the name of a Hugging Face model
  bert_layer: 8      # model layer
  methods: mai       # m = mwmf, a = inter (argmax), i = itermax
  device: cpu

aligner:
  type: llm
  model: gemma4:12b              # required
  url: http://localhost:11434
  think: false       # true = the model "thinks" before answering (much slower)
  seed: 1
  num_predict: 4096  # maximum tokens generated per verse (stops repetition loops)
```

A single command aligns, evaluates against the gold standard (CATSS),
measures performance and writes the results:

```bash
polyglot-align run experiments/glot500_vocalized.yaml
```

Results in `results/<name>/`:

| File | Contents |
|---|---|
| `config.yaml` | copy of the configuration used |
| `<passage>.jsonl` | alignments, one line per verse |
| `<passage>.csv` | review: alignment compared with CATSS and verdict (`juste` = correct, `faux` = wrong, `non aligné` = unaligned…); opens in Excel or Numbers |
| `scores.csv`, `scores.json` | measures per passage and in total (raw counts in the JSON) |
| `perf.json` | duration and CPU time per phase, cost in s / 1,000 verses, throughput, peak memory, machine and library versions |

Other commands:

```bash
polyglot-align show results/glot500_vocalized/Gen.jsonl Gen.1.1 inter    # review one verse
polyglot-align report reports/article.yaml                               # tables and figures
polyglot-align clean-gold                                                # data/gold -> data/gold_clean: builds the gold for benchmarking
polyglot-align --help
```

### 2️⃣ Python API

The same objects can be used directly, without a configuration file:

```python
from polyglot_align.store import DataStore
from polyglot_align.aligners.eflomal import EflomalAligner

store = DataStore("data")          # texts, gold and verse table, each read once

aligner = EflomalAligner(layer="w", hebrew="unvocalized", greek="unaccented")
aligner.fit(store.table_pairs())   # eflomal learns from the 22,489 verse pairs (a few seconds)

(hv, gv), = store.verse_pairs("Gen", "Gen", only="Gen.1.1")
res = aligner.align(hv, gv)
for i, j in sorted(res.links["inter"]):
    print(res.src[i], "↔", res.tgt[j])     # ב ↔ εν, ראשית ↔ αρχη, ברא ↔ εποιησεν…
```

All aligners share the same interface: `fit(verse pairs)` (does nothing for
SimAlign and the LLM), then `align(Hebrew verse, Greek verse)`, which returns
the tokens shown (`src`, `tgt`) and the links per method (`links`).

A complete experiment from Python:

```python
from polyglot_align.experiment import Experiment

scores = Experiment.from_yaml("experiments/eflomal_unvocalized.yaml").run()
print(scores["TOTAL"]["methodes"]["inter"]["mesures"])
```

Execution logs are in `logs/`.

### 3️⃣ Reproducing the results

Experiments on the whole Bible (39 passages: 36 Hebrew books, Obadiah
excluded, plus Rahlfs' double texts; Hebrew vocalized or not):

```bash
for e in eflomal glot500 mbert xlmr; do
  for v in unvocalized vocalized; do
    polyglot-align run experiments/${e}_${v}.yaml
  done
done
polyglot-align report reports/article.yaml   # -> reports/article/
```

### 4️⃣ Test app (REST API and web interface)

A web interface aligns a Hebrew text and a Greek text typed by the user,
with a choice of three algorithms (eflomal, SimAlign, LLM), and shows the
alignment as a colored interlinear. Everything runs with Docker:

```bash
docker compose up --build          # then http://localhost:8080
```

---

## 📚 Data

| Role | Source | Folder |
|---|---|---|
| Hebrew text | BHSA 2021 (ETCBC, Leningrad Codex), via Text-Fabric | `data/he/` |
| Greek text | Rahlfs' Septuagint 1935 (CenterBLC), via Text-Fabric | `data/lxx/` |
| Reference (gold) | CATSS, *Parallel Aligned Hebrew-Aramaic and Greek Texts* (Tov) | `data/gold/` (raw), `data/gold_clean/` (cleaned) |

The texts in `data/` are JSON files structured as follows:

```
{
 "Gen": {
    "1": {
      "1": {
        "t": "בְּרֵאשִׁ֖ית בָּרָ֣א אֱלֹהִ֑ים אֵ֥ת הַשָּׁמַ֖יִם וְאֵ֥ת הָאָֽרֶץ׃",
        "w": "בְּ רֵאשִׁ֖ית בָּרָ֣א אֱלֹהִ֑ים אֵ֥ת הַ שָּׁמַ֖יִם וְ אֵ֥ת הָ אָֽרֶץ",
        "l": "ב ראשׁית ברא אלהים את ה שׁמים ו את ה ארץ",
        "g": "0 0 1 2 3 4 4 5 5 6 6"
       }
     }
  }
}
```

- "t": raw text
- "w": text tokenized into words, from Text-Fabric, or by an in-house
  segmenter for new texts entered in the app
- "l": lemmatized text (not used in the end)
- "g": index of the graphic word of each token (to rebuild the raw text)

Hebrew and Greek verses are paired by a **correspondence table**,
`data/verse_map.json` (Ps 23:1 MT ↔ Ps 22:1 LXX, displaced chapters of
Jeremiah…).

For ketiv / qere, only the qere is kept (the module is only about
alignment).

The prepared data are in the repository. To regenerate them:

```bash
cd data && python export_bhsa_tf.py && python export_lxx_tf.py && cd ..    # -> data/he, data/lxx
polyglot-align clean-gold                                                  # -> data/gold_clean: prepares the gold for benchmarking
cd data && python make_verse_map.py && cd ..                               # -> data/verse_map.json: builds the Hebrew/Greek verse table
```

---

## 📏 Evaluation

CATSS aligns groups of words [**blocks**] (1 ↔ n, n ↔ 1 or n ↔ n). A
proposed link is therefore judged **correct** if it stays inside a single
CATSS block. Measures:

* **precision**: correct links / proposed links;
* **block recall**: blocks in which at least one correct link was found /
  blocks to find;
* **F1**: harmonic mean of the two;
* **non-alignments respected**: words without an equivalent (pluses and
  minuses) left without a link;
* **AER**: standard alignment error rate, for reference only.

### Current results

Whole Bible (22,489 verse pairs), BHSA words, Greek without accents,
`inter` method (unless marked `gdfa`). **Time**: training + alignment, in
seconds per 1,000 verses (`perf.json`), on the same machine (Apple M3 Max,
CPU; model loading and evaluation excluded).

| Aligner | Hebrew | Precision | Block recall | F1 | Non-alignments | Time (s / 1,000 verses) |
|---|---|---:|---:|---:|---:|---:|
| mBERT | unvocalized | 66.3 % | 52.1 % | 58.3 % | 68.3 % | 116 |
| mBERT | vocalized | 51.3 % | 50.3 % | 50.8 % | 58.3 % | 522 |
| XLM-R | unvocalized | 56.1 % | 40.6 % | 47.1 % | 74.6 % | 84 |
| XLM-R | vocalized | 34.5 % | 24.0 % | 28.3 % | 71.9 % | 301 |
| Glot500 | unvocalized | 79.6 % | 67.4 % | 73.0 % | 78.2 % | 69 |
| Glot500 | vocalized | 81.4 % | 72.4 % | 76.6 % | 76.0 % | 115 |
| eflomal | unvocalized | **97.4 %** | 93.0 % | 95.2 % | **86.7 %** | **0.33** |
| eflomal | vocalized | **97.4 %** | 92.3 % | 94.8 % | 86.6 % | **0.33** |
| eflomal (`gdfa`) | unvocalized | 94.0 % | **97.3 %** | **95.6 %** | 68.5 % | **0.33** |
| eflomal (`gdfa`) | vocalized | 93.6 % | 97.0 % | 95.3 % | 67.1 % | **0.33** |
| Gemma 4 12B (LLM, Ollama) | unvocalized | 90.2 % | 91.1 % | 90.7 % | 50.0 % | ≈ 3,900 |

- **eflomal** aligns the whole Bible (training included) in about 7 s;
  `inter` and `gdfa` come from the same run, hence the same time.
- **SimAlign**: vocalized Hebrew is slower (1.7 to 4.5 times): pointed words
  are split into more subword units.
- **LLM**: evaluated on **Genesis only** (1,518 verses; eflomal on Genesis:
  F1 95.8 %), not on the whole Bible. Time measured on the last 60 verses
  of the run (236 s, i.e. about 3.9 s per verse); the model runs in the
  Ollama server (GPU), so its CPU and memory are not counted in
  `perf.json`.

eflomal's scores drop in books where the Greek text differs considerably
from the MT: Esther (F1 80.2 %), Daniel OG (83.8 %), Job (84.5 %), Proverbs
(86.6 %), Isaiah (90.5 %).

**Note**: eflomal and LLMs are not deterministic: their scores vary
slightly from one run to the next (eflomal, Genesis: F1 from 95.7 to 95.9 %
over three runs, which is negligible).

---

## 🧩 Code organization

Package `polyglot_align` (`src/polyglot_align/`):

| Module | Contents |
|---|---|
| `config.py` | `Config`, `Passage`: reading and checking the YAML (the old flat format is converted) |
| `corpus.py` | `Corpus`, `Verse`: exported texts and their layers; `VerseMap`: verse correspondence table |
| `store.py` | `DataStore`: single access point to `data/`, each file read once |
| `normalize.py` | token normalization (vocalization, accents); letter-by-letter matching |
| `alignment.py` | `VerseAlignment`, `AlignmentRecord`: result of an aligner, JSONL format |
| `aligners/` | `Aligner` (common interface); `simalign.py`, `eflomal.py`, `llm.py`; registry `ALIGNERS` |
| `evaluation/` | `Gold` (CATSS units), `Evaluator` (link judgment, measures, CSV), `gold_clean` (cleaning of the CATSS markup) |
| `experiment.py` | `Experiment`: chains training, alignment, evaluation, writing; resuming |
| `align.py` | iteration over the verses of a passage, JSONL written verse by verse |
| `perf.py` | `PerfMeter`: duration, CPU time, memory and throughput per phase → `perf.json` |
| `report.py` | tables and figures for the paper, from `results/` |
| `segment.py`, `textalign.py` | segmentation of typed Hebrew; alignment of typed texts (test app) |
| `cli.py`, `show.py` | command line `polyglot-align` |

**Adding an alignment method**: write a subclass of `Aligner` in
`aligners/`, which declares `name` (value of `type` in the configuration),
`PARAMS` (its options and their default values) and, if needed,
`check_params`; implement `align(Hebrew verse, Greek verse)`, and
`fit(verse pairs)` if the method learns from the corpus; add it to the
`ALIGNERS` registry (`aligners/__init__.py`). The common normalization
(`hebrew`, `greek`) is provided by `Aligner.normalized_tokens`.

---

## 🧪 Tests

```bash
python -m unittest discover -s tests       # unit tests
python tests/check_non_regression.py       # non-regression
flake8                                     # style (configuration: .flake8)
```

The non-regression check re-evaluates, with the current code, the reference
alignments stored in `tests/reference/` (fast, no model): links, scores and
review CSVs must be identical.

## 👥 Authors

Developed by:

👩‍🔬 **Frédérique Michèle Rey** (Humboldt-Universität zu Berlin)
