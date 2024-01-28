ARG PYTHON_VERSION=3.11.3-slim-bullseye

FROM python:${PYTHON_VERSION} as python

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=off \
    PIP_DISABLE_PIP_VERSION_CHECK=on \
    PIP_DEFAULT_TIMEOUT=100 \
    POETRY_HOME="/opt/poetry" \
    POETRY_VIRTUALENVS_IN_PROJECT=true \
    POETRY_NO_INTERACTION=1 \
    PYSETUP_PATH="/app" \
    VENV_PATH="/app/.venv"

ENV PATH="$POETRY_HOME/bin:$VENV_PATH/bin:$PATH"


FROM python as python-build-stage

RUN apt-get update && apt-get install --no-install-recommends -y \
    curl \
    build-essential

ENV POETRY_VERSION=1.7.1
RUN curl -sSL https://install.python-poetry.org | python

WORKDIR $PYSETUP_PATH

COPY ./poetry.lock ./pyproject.toml ./
RUN poetry install --only main --no-root


FROM python as python-run-stage

COPY --from=python-build-stage $POETRY_HOME $POETRY_HOME
COPY --from=python-build-stage $PYSETUP_PATH $PYSETUP_PATH

COPY ./compose/producer/entrypoint /entrypoint
RUN sed -i 's/\r$//g' /entrypoint
RUN chmod +x /entrypoint

COPY ./compose/producer/bitstamp/start /start
RUN sed -i 's/\r$//g' /start
RUN chmod +x /start

WORKDIR $PYSETUP_PATH

COPY . .

RUN poetry install

ENTRYPOINT ["/entrypoint"]
