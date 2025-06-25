#FROM registry.access.redhat.com/ubi10/ubi@sha256:835f0c9321be6101a06c6f49049c5c197b095d704e94df69881124645e9f53a0
FROM registry.access.redhat.com/ubi9/ubi-minimal@sha256:fd6b8759fe271fcc9ff717df71ff3c3d2c42c969f00b16e8cbfabbbd30294156

ENV FLASK_APP=app.py \
    FLASK_RUN_PORT=8080 \
    FLASK_ENV=production \
    PYTHONUNBUFFERED=1

WORKDIR /app

USER 0

COPY requirements.txt .

RUN  microdnf update -y && \
    microdnf install -y tar gzip python3 python3-pip && \
    pip install --no-cache-dir --upgrade pip setuptools && \
    rm -rf /usr/lib/python3.9/site-packages/pip-*.dist-info \
    /usr/lib/python3.9/site-packages/setuptools-*.dist-info && \
    pip install --no-cache-dir -r requirements.txt && \
    microdnf clean all && \
    rm -rf /root/.cache

USER 1001

# Copiar archivos de la app
COPY app.py ./
COPY __init__.py ./
COPY static/ ./static/
COPY templates/ ./templates/

EXPOSE 8080

ENTRYPOINT ["python3"]

CMD ["app.py"]
