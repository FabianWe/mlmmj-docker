FROM ubuntu:16.04
MAINTAINER Fabian Wenzelmann <fabianwen@posteo.eu>

RUN apt-get update && apt-get install -y cron curl tar bzip2 build-essential python3

ENV PYTHONUNBUFFERED 0

# create a spool directory for mlmmj and add mlmmj user
RUN groupadd mlmmj && useradd -g mlmmj mlmmj -d /var/spool/mlmmj -m && chown -R mlmmj.mlmmj /var/spool/mlmmj

# set current mlmmj version
ENV MLMMJ_VERSION 1.3.0a1
ENV MLMMJ_PREFIX mlmmj-

RUN curl -SLO "http://mlmmj.org/releases/mlmmj-$MLMMJ_VERSION.tar.bz2"
RUN tar jxf mlmmj-$MLMMJ_VERSION.tar.bz2

WORKDIR /$MLMMJ_PREFIX$MLMMJ_VERSION

RUN ./configure && make && make install

COPY receive_listener.py /
RUN chmod +x /receive_listener.py

COPY docker_entrypoint.sh /
RUN chmod +x /docker_entrypoint.sh

RUN mkdir /mlmmj_conf/
RUN chown -R mlmmj:mlmmj /mlmmj_conf/
RUN chown -R mlmmj:mlmmj /var/spool/mlmmj

ENTRYPOINT ["/docker_entrypoint.sh"]
# TODO fix permission stuff.
CMD ["/receive_listener.py"]
