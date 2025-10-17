ARG PYTHON_VERSION=3.12.3-slim-bullseye

FROM python:${PYTHON_VERSION} AS python

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


FROM python AS python-build-stage

ARG BUILD_ENVIRONMENT=tests

RUN apt-get update && apt-get install --no-install-recommends -y \
    curl \
    build-essential \
    git

ENV POETRY_VERSION=2.1.4
RUN curl -sSL https://install.python-poetry.org | python
RUN poetry self add poetry-plugin-export  # Install export plugin (required in Poetry >=2.0)

WORKDIR $PYSETUP_PATH

COPY ./poetry.lock ./pyproject.toml ./

RUN poetry export --with dev,tests --without-hashes -f requirements.txt -o ${BUILD_ENVIRONMENT}.txt

RUN pip wheel --wheel-dir /usr/src/app/wheels -r ${BUILD_ENVIRONMENT}.txt


FROM python AS python-run-stage

RUN apt-get update && apt-get install --no-install-recommends -y \
    curl \
    build-essential \
    git

COPY --from=python-build-stage /usr/src/app/wheels /wheels

RUN pip install --no-cache-dir --no-index --find-links=/wheels/ /wheels/* && rm -rf /wheels/

COPY . .

WORKDIR $PYSETUP_PATH
