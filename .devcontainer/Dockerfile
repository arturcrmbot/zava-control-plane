FROM mcr.microsoft.com/devcontainers/python:1-3.11-bookworm

# The Yarn apt source shipped in this base image has a rotated GPG key
# (NO_PUBKEY 62D54FD4003F6525). Any downstream `apt-get update` — including
# the one run by the docker-in-docker feature install that Codespaces
# auto-injects — errors out. Remove the source so subsequent apt operations
# ignore it.
RUN rm -f /etc/apt/sources.list.d/yarn.list \
 && apt-get update \
 && apt-get clean \
 && rm -rf /var/lib/apt/lists/*
