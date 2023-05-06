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

ENV POETRY_VERSION=1.5.1
RUN curl -sSL https://install.python-poetry.org | python

WORKDIR $PYSETUP_PATH

COPY ./poetry.lock ./pyproject.toml ./

RUN poetry export --with dev,tests --without-hashes -f requirements.txt -o ${BUILD_ENVIRONMENT}.txt

RUN pip wheel --wheel-dir /usr/src/app/wheels -r ${BUILD_ENVIRONMENT}.txt


FROM python as python-run-stage

RUN apt-get update && apt-get install --no-install-recommends -y \
    curl \
    build-essential \
    git

COPY --from=python-build-stage /usr/src/app/wheels /wheels

RUN pip install --no-cache-dir --no-index --find-links=/wheels/ /wheels/* && rm -rf /wheels/

WORKDIR $PYSETUP_PATH

COPY . .
