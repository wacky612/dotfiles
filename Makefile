export PATH := .venv/bin:$(PATH)

.PHONY: prepare cmd

prepare: .venv

.venv:
	python -m venv .venv
	pip install ansible

cmd:
	ansible-playbook cmd.yml

x:
	ansible-playbook x.yml
