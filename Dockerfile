FROM python:3.11

WORKDIR /app

RUN adduser --disabled-password worker
USER worker

ENV PATH /home/worker/.local/bin:${PATH},

COPY . .
RUN pip install --no-cache-dir --upgrade -r requirements.txt

EXPOSE 5021

CMD ["uvicorn", "api:app", "--host", "0.0.0.0", "--reload", "--port", "5021"]