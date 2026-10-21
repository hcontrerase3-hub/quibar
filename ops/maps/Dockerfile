FROM debian:bookworm-slim@sha256:7ff6ba31527b9e336162fa061746c366c4b2032f4d2cff2078bea43f78efe3f8
RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates curl osmium-tool python3-mapnik python3-pil fonts-dejavu-core \
    && rm -rf /var/lib/apt/lists/*
WORKDIR /work
ENTRYPOINT []
