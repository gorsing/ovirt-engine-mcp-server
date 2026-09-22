# Build stage
FROM python:3.12-slim AS builder

# ovirt-engine-sdk-python ships an C extension (ext/ov_xml_module.c) linked
# against libxml2, so the builder needs a compiler and headers.
RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential \
        libxml2-dev \
        pkg-config \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /build

# pyproject.toml references README.md (readme = "README.md"), so both the
# metadata and the package sources must be present for `pip install .`.
COPY pyproject.toml README.md LICENSE ./
COPY ovirt_engine_mcp_server/ ovirt_engine_mcp_server/

RUN pip install --no-cache-dir --prefix=/install .

# Runtime stage
FROM python:3.12-slim

# Shared libxml2 runtime for the compiled ovirtsdk4 extension module.
RUN apt-get update && apt-get install -y --no-install-recommends \
        libxml2 \
    && rm -rf /var/lib/apt/lists/* \
    && useradd --system --no-create-home --shell /usr/sbin/nologin mcp

COPY --from=builder /install /usr/local

ENV PYTHONUNBUFFERED=1

# Run as an unprivileged user.
USER mcp

# healthcheck.py uses a relative import (from .config import ...), so it must
# run as a module; it performs a real connection test against the engine and
# exits 0 only when the API answers.
HEALTHCHECK --interval=30s --timeout=10s --retries=3 \
    CMD ["python", "-m", "ovirt_engine_mcp_server.healthcheck"]

ENTRYPOINT ["ovirt-engine-mcp"]
