venv:
	test -d venv || python3 -m venv venv && poetry install

clean:
	rm -rf venv

test:
	pytest