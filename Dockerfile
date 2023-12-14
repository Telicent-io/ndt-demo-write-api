FROM 098669589541.dkr.ecr.eu-west-2.amazonaws.com/maplib
ARG PIP_EXTRA_INDEX_URL



ENV PATH /home/worker/.local/bin:${PATH},


COPY requirements.txt .
RUN pip install  -r requirements.txt

COPY LICENSE .
COPY README.md .
COPY api.py .
COPY access.py .
COPY utils.py . 
COPY setup.cfg . 

CMD ["uvicorn", "api:app", "--host=0.0.0.0", "--port=80", "--workers=4"]