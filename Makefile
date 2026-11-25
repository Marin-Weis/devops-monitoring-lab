VENV := .venv
BIN := $(VENV)/bin

.PHONY: help setup test lint deploy redeploy load chaos reset destroy dashboard

help: ## Affiche cette aide
	@grep -E '^[a-z-]+:.*##' $(MAKEFILE_LIST) | awk -F':.*## ' '{printf "  \033[36m%-10s\033[0m %s\n", $$1, $$2}'

setup: ## Crée le venv et installe Ansible + outils de lint + collection Docker
	python3 -m venv $(VENV)
	$(BIN)/pip install -q -r requirements-dev.txt
	$(BIN)/ansible-galaxy collection install -r ansible/requirements.yml

test: ## Lance les tests unitaires de l'application
	cd app && ../$(BIN)/python -m pytest -q

lint: ## yamllint + ansible-lint
	$(BIN)/yamllint -c .yamllint.yml ansible
	cd ansible && ../$(BIN)/ansible-lint site.yml

deploy: ## Déploie toute la stack avec Ansible (idempotent)
	cd ansible && ../$(BIN)/ansible-playbook site.yml

load: ## Génère 2 minutes de trafic (10 req/s)
	$(BIN)/python scripts/loadgen.py --rps 10 --duration 120

chaos: ## Force 60 % d'erreurs pour déclencher l'alerte HighErrorRate
	curl -s -X POST http://localhost:8081/chaos/0.6

reset: ## Remet le taux d'erreurs à 5 %
	curl -s -X POST http://localhost:8081/chaos/0.05

dashboard: ## Régénère le JSON du dashboard Grafana
	$(BIN)/python scripts/generate_dashboard.py

destroy: ## Supprime conteneurs, réseau et volumes du lab
	-docker rm -f lab-app lab-prometheus lab-grafana
	-docker network rm devops-lab
	-docker volume rm lab-grafana-data lab-prometheus-data
	rm -rf .lab-data
