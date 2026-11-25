VENV := .venv
BIN := $(VENV)/bin

.PHONY: help setup test lint deploy redeploy load chaos reset destroy dashboard

help: ## Show this help
	@grep -E '^[a-z-]+:.*##' $(MAKEFILE_LIST) | awk -F':.*## ' '{printf "  \033[36m%-10s\033[0m %s\n", $$1, $$2}'

setup: ## Create venv and install Ansible + linters + Docker collection
	python3 -m venv $(VENV)
	$(BIN)/pip install -q -r requirements-dev.txt
	$(BIN)/ansible-galaxy collection install -r ansible/requirements.yml

test: ## Run application unit tests
	cd app && ../$(BIN)/python -m pytest -q

lint: ## Run yamllint and ansible-lint
	$(BIN)/yamllint -c .yamllint.yml ansible
	cd ansible && ../$(BIN)/ansible-lint site.yml

deploy: ## Deploy the full stack with Ansible (idempotent)
	cd ansible && ../$(BIN)/ansible-playbook site.yml

load: ## Generate 2 minutes of traffic (10 req/s)
	$(BIN)/python scripts/loadgen.py --rps 10 --duration 120

chaos: ## Force 60% HTTP 500 errors to trigger HighErrorRate alert
	curl -s -X POST http://localhost:8081/chaos/0.6

reset: ## Reset simulated error rate to 5%
	curl -s -X POST http://localhost:8081/chaos/0.05

dashboard: ## Regenerate Grafana dashboard JSON
	$(BIN)/python scripts/generate_dashboard.py

destroy: ## Remove lab containers, network, volumes, and rendered configs
	-docker rm -f lab-app lab-prometheus lab-grafana
	-docker network rm devops-lab
	-docker volume rm lab-grafana-data lab-prometheus-data
	rm -rf .lab-data
