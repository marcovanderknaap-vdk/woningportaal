#!/usr/bin/env bash
# Hulpscript voor de beheeromgeving in GitHub Codespaces.
#   bash scripts/beheer.sh voorbereiden   – database uit branch 'data' ophalen
#   bash scripts/beheer.sh start          – website + backend starten op poort 8000
#   bash scripts/beheer.sh bewaren        – gewijzigde makelaars opslaan in makelaars.json en pushen
set -euo pipefail
cd "$(dirname "$0")/.."

case "${1:-start}" in
  voorbereiden)
    if [ ! -d databranch ]; then
      if git ls-remote --exit-code --heads origin data >/dev/null 2>&1; then
        git fetch --depth 1 origin data && git worktree add databranch origin/data
      else
        mkdir -p databranch
      fi
    else
      (cd databranch && git fetch --depth 1 origin data && git checkout -q --detach origin/data) || true
    fi
    python manage.py migrate --noinput
    python manage.py makelaars_laden --niet-bijwerken
    if ! python manage.py shell -c "from django.contrib.auth.models import User; exit(0 if User.objects.exists() else 1)" 2>/dev/null; then
      if [ -t 0 ]; then
        echo "Maak een beheerder aan:"
        python manage.py createsuperuser
      else
        echo ">>> Nog geen beheerder. Typ in de terminal: python manage.py createsuperuser"
      fi
    fi
    ;;
  start)
    python manage.py runserver 0.0.0.0:8000
    ;;
  bewaren)
    python manage.py makelaars_exporteren
    git add makelaars.json
    git commit -m "Makelaars bijgewerkt via beheer" && git push
    ;;
esac
