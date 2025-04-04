FROM python:3.9 

WORKDIR /usr/src/app

COPY ./req.txt ./
RUN apt-get update && apt-get install qemu-utils --yes
RUN pip install -r req.txt

COPY ./* ./
COPY ./lib/* ./lib/

CMD [ "python" , "./run.py" ,"-v","1" ]

