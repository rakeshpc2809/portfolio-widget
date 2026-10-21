.PHONY: all test lint install uninstall auth inspect fetch mock status hydrate clean

all: lint test

test:
	pytest -v

lint:
	ruff check .

install:
	bash install.sh

uninstall:
	bash install.sh --uninstall

auth:
	./src/indmoney-sync auth

inspect:
	./src/indmoney-sync inspect

hydrate:
	./src/indmoney-sync hydrate

fetch:
	./src/indmoney-sync fetch --force -v

mock:
	./src/indmoney-sync mock

status:
	./src/indmoney-sync status

clean:
	rm -rf __pycache__ src/indmoney_sync/__pycache__ tests/__pycache__ .pytest_cache
