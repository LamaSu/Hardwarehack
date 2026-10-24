# Claude Code + uv workspace for the Hardwarehack repo.
FROM node:22-bookworm-slim

RUN apt-get update \
    && apt-get install -y --no-install-recommends git ca-certificates curl \
    && rm -rf /var/lib/apt/lists/*

RUN npm install -g @anthropic-ai/claude-code

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /usr/local/bin/

# The repo is bind-mounted from Windows: trust it and keep LF line endings.
RUN git config --system --add safe.directory '*' \
    && git config --system core.autocrlf input

# Claude Code doesn't allow skipping permissions as root, so work as a normal user.
RUN useradd -m -s /bin/bash dev
USER dev

# Keep the Linux venv out of the mounted folder so it doesn't clash with the Windows .venv.
ENV UV_PROJECT_ENVIRONMENT=/home/dev/.venvs/drug-screen-platform \
    UV_PYTHON_INSTALL_DIR=/home/dev/.uv-python

WORKDIR /workspace
CMD ["bash"]
