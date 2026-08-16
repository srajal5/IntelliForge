.PHONY: install test health stats validate pipeline pipeline-full export benchmark resolve

PYTHON ?= python
LIMIT  ?= 10
RECORDS ?= 100
WORKERS ?= 5

install:
	$(PYTHON) -m pip install -r requirements.txt

test:
	$(PYTHON) -m src.main test

health:
	$(PYTHON) -m src.main health

stats:
	$(PYTHON) -m src.main stats

validate:
	$(PYTHON) -m src.main validate

pipeline:
	$(PYTHON) -m src.main pipeline --limit $(LIMIT) --workers $(WORKERS)

pipeline-full:
	$(PYTHON) -m src.main pipeline --limit 100 --workers $(WORKERS)

research:
	$(PYTHON) -m src.main research --limit $(LIMIT)

startups:
	$(PYTHON) -m src.main startups --limit $(LIMIT)

products:
	$(PYTHON) -m src.main products --limit $(LIMIT)

news:
	$(PYTHON) -m src.main news --limit $(LIMIT)

jobs:
	$(PYTHON) -m src.main jobs --limit $(LIMIT)

resolve:
	$(PYTHON) -m src.main resolve

export:
	$(PYTHON) -m src.main export

benchmark:
	$(PYTHON) -m src.main benchmark --records $(RECORDS)
