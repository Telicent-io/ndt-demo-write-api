FROM python:3.11-slim
ARG PIP_EXTRA_INDEX_URL

WORKDIR /app

ENV PATH /home/worker/.local/bin:${PATH},
COPY start.sh .
RUN chmod +x start.sh

COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade -r requirements.txt

COPY LICENSE .
COPY README.md .
COPY api.py .
COPY access.py .
COPY utils.py . 
COPY setup.cfg . 

CMD "./start.sh"