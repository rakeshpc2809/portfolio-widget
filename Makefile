.PHONY: all test install auth inspect fetch mock status hydrate clean

all: test

test:
	python3 -m unittest discover -s tests

install:
	bash install.sh

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
	rm -rf __pycache__ src/indmoney_sync/__pycache__ tests/__pycache__
