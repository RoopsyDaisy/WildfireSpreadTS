FROM docker.io/nvidia/cuda:12.4.0-runtime-ubuntu22.04

ENV DEBIAN_FRONTEND=noninteractive

# -----------------------------------------------------------------------------
# Base system packages
# -----------------------------------------------------------------------------
# Python 3.10 is the default on ubuntu 22.04 — matches WSTS+'s tested setup.
# GDAL/PROJ/NetCDF for geospatial + WRF NetCDF reading.
# Node for the Claude Code CLI; ffmpeg/rsync are commonly useful.
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        bash \
        python3 python3-pip python3-dev \
        build-essential git \
        gdal-bin libgdal-dev proj-bin libproj-dev \
        libnetcdf-dev libhdf5-dev \
        ffmpeg \
        rsync \
        openssh-client \
        sudo \
        curl \
        ca-certificates && \
    rm -rf /var/lib/apt/lists/*

# -----------------------------------------------------------------------------
# Node.js 20 (for Claude Code CLI)
# -----------------------------------------------------------------------------
RUN curl -fsSL https://deb.nodesource.com/setup_20.x | bash - && \
    apt-get install -y --no-install-recommends nodejs && \
    rm -rf /var/lib/apt/lists/*

# -----------------------------------------------------------------------------
# Python dependency manager (uv)
# -----------------------------------------------------------------------------
RUN curl -LsSf https://astral.sh/uv/install.sh | sh \
    && mv /root/.local/bin/uv /usr/local/bin/uv

# -----------------------------------------------------------------------------
# Claude Code CLI
# -----------------------------------------------------------------------------
RUN npm install -g @anthropic-ai/claude-code

# -----------------------------------------------------------------------------
# Unprivileged user (UID/GID rewritten by dev-containers at runtime)
# -----------------------------------------------------------------------------
ARG USERNAME=vscode
RUN useradd -m "$USERNAME" && \
    echo "$USERNAME ALL=(ALL) NOPASSWD:ALL" >> /etc/sudoers

WORKDIR /workspace
USER ${USERNAME}

CMD ["/bin/bash"]
