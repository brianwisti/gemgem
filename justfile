play:
	python pygame_gem.py

check:
	prospector --strictness high --with-tool mypy pygame_gem.py

test:
	pytest -x
