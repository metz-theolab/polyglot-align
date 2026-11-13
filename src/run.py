"""Lance une expérience décrite dans un fichier YAML (voir experiment.py).

Usage (depuis la racine du projet) : python src/run.py experiments/<nom>.yaml
"""
import sys

from experiment import Experiment

if __name__ == "__main__":
    Experiment.from_yaml(sys.argv[1] if len(sys.argv) > 1 else "config.yaml").run()
