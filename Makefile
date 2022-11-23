.PHONY: cmd x

cmd:
	ansible-playbook --diff cmd.yml

x:
	ansible-playbook --diff x.yml
