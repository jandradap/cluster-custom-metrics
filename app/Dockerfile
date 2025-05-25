FROM registry.access.redhat.com/ubi9/python-311:9.6-1747333117

ENV FLASK_APP=app.py \
    FLASK_RUN_PORT=8080 \
    FLASK_ENV=production \
    PYTHONUNBUFFERED=1

WORKDIR /app

USER 0

RUN dnf update -y && \
    curl -sL https://mirror.openshift.com/pub/openshift-v4/clients/ocp/latest/openshift-client-linux.tar.gz \
    | tar -xz -C /usr/local/bin oc && \
    chmod +x /usr/local/bin/oc && \
    #CVE
    pip install --upgrade pip setuptools && \
    pip install --no-cache-dir flask==3.1.1 prometheus_client==0.22.0 && \
    rm -rf /root/.cache

USER 1001

# Copiar archivos de la app
COPY app.py ./
COPY static/ ./static/

EXPOSE 8080

# HEALTHCHECK --interval=30s --timeout=3s CMD curl -f http://localhost:8080/metrics || exit 1

ENTRYPOINT ["python"]

CMD ["app.py"]