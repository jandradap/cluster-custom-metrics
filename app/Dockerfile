FROM registry.access.redhat.com/ubi10/ubi@sha256:835f0c9321be6101a06c6f49049c5c197b095d704e94df69881124645e9f53a0

ENV FLASK_APP=app.py \
    FLASK_RUN_PORT=8080 \
    FLASK_ENV=production \
    PYTHONUNBUFFERED=1

WORKDIR /app

USER 0

COPY requirements.txt .

RUN  dnf update -y && \
    dnf install -y python3 python3-devel python3-pip && \
    pip install --no-cache-dir -r requirements.txt && \
    dnf clean all && \
    rm -rf /root/.cache

#oc
RUN curl -sL https://mirror.openshift.com/pub/openshift-v4/clients/ocp/latest/openshift-client-linux.tar.gz \
    | tar -xz -C /usr/local/bin oc && \
    chmod +x /usr/local/bin/oc

USER 1001

# Copiar archivos de la app
COPY app.py ./
COPY static/ ./static/

EXPOSE 8080

ENTRYPOINT ["python3"]

CMD ["app.py"]