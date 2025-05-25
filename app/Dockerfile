FROM registry.access.redhat.com/ubi9/python-311:9.6-1747333117

ENV FLASK_APP=app.py \
    FLASK_RUN_PORT=8080 \
    FLASK_ENV=production \
    PYTHONUNBUFFERED=1

WORKDIR /app

USER 0

COPY requirements.txt .

RUN dnf update -y && \
    curl -sL https://mirror.openshift.com/pub/openshift-v4/clients/ocp/latest/openshift-client-linux.tar.gz \
    | tar -xz -C /usr/local/bin oc && \
    chmod +x /usr/local/bin/oc && \
    #CVE
    pip install --no-cache-dir -r requirements.txt && \
    rm -rf /usr/lib/python3.9/site-packages/urllib3-1.26.5-py3.9.egg-info && \
    rm -rf /usr/lib/python3.9/site-packages/requests-2.25.1.dist-info && \
    rm -rf /usr/lib/python3.11/site-packages/pip-22.3.1.dist-info && \
    rm -rf /usr/lib/python3.9/site-packages/idna-2.10-py3.9.egg-info && \
    rm -rf /usr/lib/python3.9/site-packages/setuptools-53.0.0.dist-info && \
    rm -rf /usr/lib/python3.11/site-packages/setuptools-65.5.1.dist-info && \
    rm -rf /root/.cache



USER 1001

# Copiar archivos de la app
COPY app.py ./
COPY static/ ./static/

EXPOSE 8080

# HEALTHCHECK --interval=30s --timeout=3s CMD curl -f http://localhost:8080/metrics || exit 1

ENTRYPOINT ["python"]

CMD ["app.py"]