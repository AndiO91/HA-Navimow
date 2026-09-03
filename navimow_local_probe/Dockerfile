ARG BUILD_FROM
FROM ${BUILD_FROM}

RUN apk add --no-cache \
        avahi-tools \
        bind-tools \
        iproute2 \
        nmap \
        openssl

COPY lib.sh /usr/lib/navimow-local-probe.sh
COPY run.sh /run.sh
RUN chmod 0755 /run.sh /usr/lib/navimow-local-probe.sh

CMD ["/run.sh"]
