pre-commit:
	@pre-commit run --color=always --all-files

pre-commit-verify:
	@docker-compose -f local.yml run --rm tests bash -c \
"git config --global --add safe.directory /app && \
git init && \
git add . && \
pre-commit run --color=always --show-diff-on-failure --all-files"

tests:
	@docker-compose -f local.yml run --rm tests pytest

tests-ssh:
	@docker-compose -f local.yml run tests bash

tests-shell:
	@docker-compose -f local.yml run --rm tests ipython

coverage:
	@docker-compose -f local.yml run --rm tests bash -c \
"coverage run -m pytest -v --tb=short -p no:warnings && \
coverage report && \
coverage html"
	open htmlcov/index.html

benchmark:
	@cd benchmarks && sh endpoints.sh && cd ..

reset-data:
	@docker exec -it exchange-radar-redis redis-cli -n 0 FLUSHDB ASYNC
