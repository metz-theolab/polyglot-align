"""Ligne de commande `polyglot-align` (à lancer depuis la racine du projet).

    polyglot-align run experiments/<nom>.yaml           aligner et évaluer -> results/<nom>/
                                                        (reprend une exécution interrompue)
    polyglot-align run --force experiments/<nom>.yaml   repartir de zéro
    polyglot-align report reports/article.yaml          tableaux et figures -> reports/<nom>/
    polyglot-align show results/<nom>/Gen.1.jsonl Gen.1.1 [méthode]
                                                        relire l'alignement d'un verset
    polyglot-align clean-gold                           data/gold -> data/gold_clean

Équivalent sans installation de la commande : python -m polyglot_align …

La bibliothèque écrit dans le journal (logging) ; la ligne de commande
l'affiche dans le terminal.
"""
import argparse
import logging
import sys


def setup_logging() -> None:
    """Journal de polyglot_align (seulement lui : pas celui de transformers,
    matplotlib…) affiché sur la sortie standard, message seul, comme les
    anciens print."""
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(logging.Formatter("%(message)s"))
    log = logging.getLogger("polyglot_align")
    log.addHandler(handler)
    log.setLevel(logging.INFO)
    log.propagate = False


def main(argv=None) -> None:
    parser = argparse.ArgumentParser(prog="polyglot-align", description=__doc__.split("\n")[0])
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("run", help="lancer une expérience (aligner, évaluer, écrire les résultats)")
    p.add_argument("config", help="fichier YAML de l'expérience (experiments/<nom>.yaml)")
    p.add_argument("--force", action="store_true",
                   help="repartir de zéro : effacer les résultats précédents de results/<nom>/")

    p = sub.add_parser("report", help="produire les tableaux et figures de l'article")
    p.add_argument("spec", nargs="?", default="reports/article.yaml", help="fichier YAML du rapport")

    p = sub.add_parser("show", help="afficher l'alignement d'un verset")
    p.add_argument("jsonl", help="results/<nom>/<passage>.jsonl")
    p.add_argument("ref", help="référence hébraïque, ex. Gen.1.1")
    p.add_argument("method", nargs="?", default="inter", help="méthode (inter, itermax, gdfa, llm…)")

    sub.add_parser("clean-gold", help="nettoyer le gold CATSS : data/gold -> data/gold_clean")

    args = parser.parse_args(argv)
    setup_logging()
    if args.command == "run":
        from polyglot_align.experiment import Experiment
        Experiment.from_yaml(args.config, force=args.force).run()
    elif args.command == "report":
        from polyglot_align.report import Report
        Report.from_yaml(args.spec).run()
    elif args.command == "show":
        from polyglot_align.show import show
        print(show(args.jsonl, args.ref, args.method))
    elif args.command == "clean-gold":
        from polyglot_align.evaluation.gold_clean import main as clean_gold
        clean_gold()


if __name__ == "__main__":
    main()
