#!/bin/zsh
# Lance à la suite les expériences sur toute la Bible, sans mise en veille du Mac.
# Usage (depuis la racine du projet) :  zsh scripts/run_night.sh
#   ou avec une autre liste :           zsh scripts/run_night.sh glot500_vocalized mbert_vocalized
# Journal de chaque expérience : logs/<nom>.log ; bilan : logs/bilan.txt
# Une expérience qui échoue n'arrête pas les suivantes.

cd "$(dirname "$0")/.." || exit 1
RUN=venv/bin/polyglot-align   # installé par : pip install -e .

EXPERIMENTS=(
  eflomal_unvocalized eflomal_vocalized     # quelques minutes
  glot500_vocalized glot500_unvocalized     # meilleur modèle neuronal d'abord
  mbert_vocalized mbert_unvocalized
  xlmr_vocalized xlmr_unvocalized
)
(( $# > 0 )) && EXPERIMENTS=("$@")

mkdir -p logs
echo "Début : $(date '+%F %T')" > logs/bilan.txt

for e in $EXPERIMENTS; do
  echo "[$(date '+%T')] $e …"
  # caffeinate -i -s : empêche la veille tant que la commande tourne (-s : seulement sur secteur)
  if caffeinate -i -s $RUN run experiments/$e.yaml > logs/$e.log 2>&1; then
    result=OK
  else
    result="ÉCHEC (voir logs/$e.log)"
  fi
  echo "$(date '+%F %T')  $e  $result" | tee -a logs/bilan.txt
done

echo "Fin : $(date '+%F %T')" >> logs/bilan.txt
