# Core API image (no Streamlit). Build ON the LinuxONE host so the image is s390x:  docker build -t loanlens .
# Use an image that publishes s390x variants (python:3.11-slim does). If numpy/scikit-learn wheels are not
# available for your Python version the build may compile from source; see docs/DEPLOY_LINUXONE.md.
FROM python:3.11-slim
WORKDIR /app
COPY requirements-core.txt .
RUN pip install --no-cache-dir -r requirements-core.txt
COPY loanlens loanlens
COPY scripts scripts
ENV LOANLENS_ARTIFACTS=/data LOANLENS_DATASET=auto
VOLUME /data
EXPOSE 8000
# Train on first start (on this architecture), then serve. Set LOANLENS_REVIEWER_TOKEN at run time.
CMD ["sh", "-c", "python -m loanlens.train --dataset ${LOANLENS_DATASET} && python -m loanlens.server --host 0.0.0.0 --port 8000"]
