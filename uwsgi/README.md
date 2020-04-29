# Running darksky-api Flask Application With Podman

Set up a directory structure on the host where you will run the application:

    /opt/uwsgi
         ├── darksky-api
         │   ├── ClimacellWeatherAPI.py
         │   ├── DarkskyAPIFunctions.py
         │   ├── darksky-api.py
         │   ├── NOAAWeatherAPI.py
         │   └── static
         │       └── favicon.ico
         ├── darksky-api.service
         ├── Dockerfile
         └── uwsgi.d
             └── darksky-api.ini

Use the Dockerfile to create a uWSGI container on the host where you will run the application:

    sudo podman build -t darksky-api -f /opt/uwsgi/Dockerfile
    
Copy /opt/uwsgi/darksky-api.service to /etc/systemd/system/darksky-api.service and
 
    $ sudo systemctl daemon-reload
    $ sudo systemctl enable darksky-api.service
    $ sudo systemctl start darksky-api.service
    
The service will accept requests on the ports mapped in the podman command line in darksky-api.service.  Port 5080 is the HTTP port for weather API calls.  Port 9191 is the Flask application's status port.  You should only  allow outside access to the HTTP port.  Port 9191 can be accessed locally from the podman container's host to monitor the application.
 
The service writes log file output to /opt/uwsgi/darksky-api/darksky-api.log.  This includes elapsed time to respond to each API call it receives, error information, and information about weather icon images it was not able to handle properly, i.e., that are not defined properly in the icon mapping functions in the app.
 
uWSGI writes console log output into the /opt/uwsgi/darksky-api/uwsgi.log file. 

When updates are made to the application's code, the new files can be copied into place in the directory structure shown above while the application continues to run.  Use the `touch /opt/uwsgi/uwsgi.d/darksky-api.ini` command to make uwsgi reload the application code and pick up the changes.

## Useful podman commands

    sudo podman build -t darksky-api -f /opt/darksky-api/Dockerfile

    sudo podman run --interactive --name=darksky-api --rm --tty --volume=/opt/uwsgi/darksky-api:/opt/uwsgi --volume=/opt/uwsgi/uwsgi.d:/etc/uwsgi.d --publish=5080:5080/tcp --publish=9191:9191/tcp localhost/darksky-api:latest /bin/sh

    sudo podman run --detach --name=darksky-api --rm --volume=/opt/uwsgi/darksky-api:/opt/uwsgi --volume=/opt/uwsgi/uwsgi.d:/etc/uwsgi.d --publish=5080:5080/tcp --publish=9191:9191/tcp localhost/darksky-api:latest

    sudo podman images
    sudo podman rmi <image>

    sudo podman ps -a
    sudo podman stop <id>
    sudo podman rm <id>

    sudo /usr/local/bin/uwsgi --ini /etc/uwsgi.ini --pidfile /run/uwsgi/uwsgi.pid --stats /run/uwsgi/stats.sock
