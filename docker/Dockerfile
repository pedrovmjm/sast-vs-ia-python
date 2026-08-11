FROM --platform=linux/amd64 python:3.12.13-slim-bookworm@sha256:6e13e65c55e33adf203d77ee371cf8bf5d81bd4902ef07565721f46bf44917af

LABEL org.opencontainers.image.title="TCC SAST harness"
LABEL org.opencontainers.image.version="2026-08-10"

ENV HOME=/tmp/tcc-home \
    LANG=C.UTF-8 \
    LC_ALL=C.UTF-8 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONNOUSERSITE=1 \
    PYTHONSAFEPATH=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/opt/tcc \
    SEMGREP_ENABLE_VERSION_CHECK=0 \
    SEMGREP_SEND_METRICS=off

RUN groupadd --gid 10001 tcc \
    && useradd --uid 10001 --gid 10001 --no-create-home \
        --home-dir /nonexistent --shell /usr/sbin/nologin tcc \
    && install -d -o 10001 -g 10001 /workspace /saida /opt/tcc

COPY docker/requirements.lock /opt/tcc/requirements.lock

RUN python -m pip install \
        --no-cache-dir \
        --disable-pip-version-check \
        --only-binary=:all: \
        --require-hashes \
        --requirement /opt/tcc/requirements.lock

COPY docker/requirements.in docker/requirements.lock /opt/tcc/docker/
COPY --chown=10001:10001 runner/ /opt/tcc/runner/
COPY --chown=10001:10001 config/ /opt/tcc/config/

USER 10001:10001
WORKDIR /opt/tcc

CMD ["python", "-c", "import platform; print(platform.python_version())"]
