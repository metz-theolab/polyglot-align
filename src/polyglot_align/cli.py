"""Ligne de commande `polyglot-align` (à lancer depuis la racine du projet).

    polyglot-align run experiments/<nom>.yaml           aligner et évaluer -> results/<nom>/
    polyglot-align report reports/article.yaml          tableaux et figures -> reports/<nom>/
    polyglot-align show results/<nom>/Gen.1.jsonl Gen.1.1 [méthode]
                                                        relire l'alignement d'un verset
    polyglot-align clean-gold                           data/gold -> data/gold_clean

Équivalent sans installation de la commande : python -m polyglot_align …
"""
import argparse


def main(argv=None) -> None:
    parser = argparse.ArgumentParser(prog="polyglot-align", description=__doc__.split("\n")[0])
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("run", help="lancer une expérience (aligner, évaluer, écrire les résultats)")
    p.add_argument("config", help="fichier YAML de l'expérience (experiments/<nom>.yaml)")

    p = sub.add_parser("report", help="produire les tableaux et figures de l'article")
    p.add_argument("spec", nargs="?", default="reports/article.yaml", help="fichier YAML du rapport")

    p = sub.add_parser("show", help="afficher l'alignement d'un verset")
    p.add_argument("jsonl", help="results/<nom>/<passage>.jsonl")
    p.add_argument("ref", help="référence hébraïque, ex. Gen.1.1")
    p.add_argument("method", nargs="?", default="inter", help="méthode (inter, itermax, gdfa, llm…)")

    sub.add_parser("clean-gold", help="nettoyer le gold CATSS : data/gold -> data/gold_clean")

    args = parser.parse_args(argv)
    if args.command == "run":
        from polyglot_align.experiment import Experiment
        Experiment.from_yaml(args.config).run()
    elif args.command == "report":
        from polyglot_align.report import Report
        Report.from_yaml(args.spec).run()
    elif args.command == "show":
        from polyglot_align.show import show
        show(args.jsonl, args.ref, args.method)
    elif args.command == "clean-gold":
        from polyglot_align.evaluation.gold_clean import main as clean_gold
        clean_gold()


if __name__ == "__main__":
    main()
