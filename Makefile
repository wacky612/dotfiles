export PATH := .venv/bin:$(PATH)

.PHONY: prepare

prepare: .venv

.venv:
	python -m venv .venv
	pip install ansible
