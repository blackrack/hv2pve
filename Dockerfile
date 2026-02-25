FROM python:3.15.0a6-slim-trixie

WORKDIR /usr/src/app

RUN apt-get update && apt-get install qemu-utils build-essential  libffi-dev --yes
COPY ./req.txt ./
RUN pip install -r req.txt

COPY . .

CMD [ "python" , "./run.py" ,"-v","1" ]

