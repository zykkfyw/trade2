FROM ubuntu
WORKDIR  /
COPY app.py ./trade/app.py
COPY trading_bot.py ./trade/trading_bot.py
RUN apt-get update
RUN apt-get install -y curl
RUN apt-get install -y python3
RUN apt-get install -y python3-pip
RUN apt-get install -y net-tools
RUN apt-get install -y iputils-ping
RUN apt-get install -y openssh-server
RUN pip3 install flask
RUN pip3 install alpaca-trade-api
RUN apt-get install nano 
RUN chmod +x ./trade/app.py
RUN chmod +x ./trade/trading_bot.py
EXPOSE 5000/tcp
EXPOSE 5000/udp
CMD ["python3", "./trade/app.py"]