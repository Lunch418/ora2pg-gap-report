# ora2pg-gap-report with everything --migrate needs: ora2pg 25.0 (the
# version every gap in the registry was confirmed on), psql for
# --load-check against a connection string, and the docker CLI for
# --load-check docker through the host's socket.
#
#   docker run --rm -v "$PWD:/work" ghcr.io/lunch418/ora2pg-gap-report schema/
#   docker run --rm -v "$PWD:/work" -v /var/run/docker.sock:/var/run/docker.sock \
#       ghcr.io/lunch418/ora2pg-gap-report --migrate out/ --load-check docker schema/

FROM docker:27-cli AS docker-cli

FROM python:3.12-slim-bookworm

# ora2pg from source, pinned by commit like the CI job that tests against
# it: a git object id fixes the content, a tag can be moved.
ARG ORA2PG_COMMIT=77201cb9c00f140422db88decc109a8efbe8eba6
ARG ORA2PG_VERSION=25.0
RUN apt-get update -qq \
 && apt-get install -y --no-install-recommends perl libdbi-perl make git ca-certificates postgresql-client \
 && git init -q /tmp/ora2pg && cd /tmp/ora2pg \
 && git remote add origin https://github.com/darold/ora2pg.git \
 && git fetch -q --depth 1 origin "${ORA2PG_COMMIT}" && git checkout -q FETCH_HEAD \
 && grep -q "VERSION *= *'${ORA2PG_VERSION}'" lib/Ora2Pg.pm \
 && perl Makefile.PL && make && make install \
 && install -Dm644 /etc/ora2pg/ora2pg.conf.dist /etc/ora2pg/ora2pg.conf \
 && cd / && rm -rf /tmp/ora2pg \
 && apt-get purge -y git make && apt-get autoremove -y && rm -rf /var/lib/apt/lists/*

COPY --from=docker-cli /usr/local/bin/docker /usr/local/bin/docker

COPY . /src
RUN pip install --no-cache-dir /src && rm -rf /src

# English unless --lang or ORA2PG_GAP_REPORT_LANG says otherwise: the tool
# defaults to Russian, which an image used from anywhere should not assume.
ENV ORA2PG_GAP_REPORT_LANG=en
WORKDIR /work
ENTRYPOINT ["ora2pg-gap-report"]
CMD ["--help"]
