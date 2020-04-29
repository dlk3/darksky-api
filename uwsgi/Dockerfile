FROM docker.io/library/fedora:31
RUN dnf upgrade -y
RUN dnf groupinstall -y "C Development Tools and Libraries"
RUN dnf install -y python3-devel
RUN dnf clean all
RUN pip install --upgrade pip
RUN pip install flask requests geopy isodate pytz astral timezonefinder uwsgi
RUN groupadd uwsgi
RUN useradd --system --shell /bin/false --gid uwsgi uwsgi
RUN mkdir -m 777 /opt/uwsgi
RUN chown uwsgi:uwsgi /opt/uwsgi
RUN mkdir -m 755 /run/uwsgi
RUN chown uwsgi:uwsgi /run/uwsgi
RUN mkdir /etc/uwsgi.d
RUN chown uwsgi:uwsgi /etc/uwsgi.d
RUN echo -e "[uwsgi]\nuid = uwsgi\ngid = uwsgi\npidfile = /run/uwsgi/uwsgi.pid\n\
stats = /run/uwsgi/stats.sock\nchmod-socket = 660\nemperor = /etc/uwsgi.d\n\
cap = setgid,setuid\nenable-threads = true\n\
logger = file:logfile=/opt/uwsgi/uwsgi.log,maxsize=2000000" >/etc/uwsgi.ini
VOLUME /opt/uwsgi
VOLUME /etc/uwsgi.d
EXPOSE 5080/tcp
EXPOSE 9191/tcp
ENTRYPOINT /usr/local/bin/uwsgi --ini /etc/uwsgi.ini --pidfile /run/uwsgi/uwsgi.pid --stats /run/uwsgi/stats.sock
