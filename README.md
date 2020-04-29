This is a weather forecasting web service that provides the same information that has been available from the [DarkSky API](https://darksky.net/dev).  DarkSky has recently been acquired by Apple and has announced that their API will continue to be available for currently registered users until June 2021, with no new registrations being accepted between now and then.  When that service disappears I'll need something else to support the weather widgets that I built for the video dashboard in my home.

This Python Flask-based web service uses free weather data from the [NOAA Weather API](https://www.weather.gov/documentation/services-web-api) and [Climacell MicroWeather API](https://www.climacell.co/weather-api/) and returns that data in the same JSON format that the [DarkSky API](https://darksky.net/dev) used.  This web service also uses the same request URL format that DarkSky used:

     http://<hostname.domainname>:<port>/forecast/<Climacell-API-key>/<latitude>,<longitude>

The code is modularized so that other weather services could be added or removed in the future.  A design assumption is that the [NOAA Weather API](https://www.weather.gov/documentation/services-web-api) web service should continue to exist for a long period of time, as-is.  The application is designed to use that service to build as complete a response as possible, one that could stand on its own, and then to replace/extend that response using additional service(s) like Climacell.  The [Climacell MicroWeather API](https://www.climacell.co/weather-api/) service is assumed to be less stable than NOAA, more likely to change or disappear in the future like DarkSky is.

The NOAA service is not completely reliable.  There will be instances when a call to one or more of its web services returns no data or returns an error.  The NOAAWeatherAPI.py module is intended to absorb these instances, usually returning an empty response and logging a message when they occur.  The modules that darksky-api.py calls after NOAAWeatherAPI.py, like ClimacellWeatherAPI.py, need to be designed to deal with the possibility that they may receive no input data and decide how to respond in that case.  ClimacellWeatherAPI.py attempts to build and return a response based solely on Climacell data.

The [NOAA Weather API](https://www.weather.gov/documentation/services-web-api) is free to use.  No registration or API key is necessary.  They do ask that the UserAgent header be set on each request so that they have some means to contact someone if there are issues.  There's a variable very near the top of the darksky-api.py file where a string can be set for this purpose.  See the "Authorization" paragraph on the [NOAA Weather API Web Service page](https://www.weather.gov/documentation/services-web-api) for a description of what NOAA is looking for here.  I have not found any information on rate limits for these services but they only update once an hour so there's no point in hammering away at them.

The [Climacell MicroWeather API](https://www.climacell.co/weather-api/) is a paid service but there is a free option for developers that has limited capabilities and usage limits.  A free account gets 1000 API calls per day.  This script makes four API calls every time it runs.  It needs to call four different Climacell services to collect the daily, hourly and minute-by-minute forecasts, and the current conditions data that it needs.  That means the script could be run a maximum of 250 times per day or once every 5 minutes 46 seconds.  My family dashboard has been doing one call to the DarkSky API every 30 minutes.  That would be equivelent to 192 Climacell API calls per day.

There are some gaps in the data that NOAA/Climacell can provide versus DarkSky.  These are marked in the source code, in NOAAWeatherAPI.py and ClimacellWeatherAPI.py.  In summary:

- There is no "nearestStormDistance" and "nearestStormBearing" data.
- There is no "precipProbability" data in the "currently" section or "minutely" forecasts section.
- There is no "precipType" data in the "daily" forecasts section.
- There is no "uvIndex" data.

For more information on these APIs, see:

- [DarkSky's API](https://darksky.net/dev/docs)
- [NOAA's Weather API Web Service](https://www.weather.gov/documentation/services-web-api)
- [Climacell's MicroWeather API](https://www.climacell.co/weather-api/docs/)

### Installation

This script is written for Python version 3.  It uses the Astral module whose RPM package is out of date on Fedora 31 where I work.  It also uses the timezonefinder module which is not packaged for Fedora.  Therefore I chose to run this service in a Python virtual environment where I can install modules at will without affecting the rest of my system.  Here's the one-time setup procedure I used to create that virtual environment, with the necessary modules installed, in the home directory of my regular userid:

    $ sudo yum install python3 python3-virtualenv python3-flask
    $ python -m venv darksky-api-venv
    $ source darksky-api-venv/bin/activate
    (darksky-api-venv) $ pip install --upgrade pip
    (darksky-api-venv) $ pip install flask requests geopy isodate pytz astral timezonefinder
    (darksky-api-venv) $ deactivate

To run the darksky-api Flask web service in development mode I do:

    $ cd <path-where-darkski-api.py-lives>
    $ source ${HOME}/darksky-api-venv/bin/activate
    (darksky-api-venv) $ export FLASK_ENV=development
    (darksky-api-venv) $ export FLASK_APP=darksky-api.py
    (darksky-api-venv) $ flask run

The web service is then available at this URL:

    http://localhost:5000/forecast/<Climacell-API-key>/<latitude>,<longitude>

When I'm finished:

    Ctrl-C to terminate flask
    (darksky-api-venv) $ deactivate

The application will log messages into a darksky-api.log file in the current directory.  It will also write some messages to the development console.

The [Flask documentation](https://flask.palletsprojects.com/en/1.1.x/deploying/#deployment) discusses the many options for deploying a Flask application in production.  I use the uwsgi service running inside a Fedora podman container to host the application.


### License

This Source Code Form is subject to the terms of the Mozilla Public
License, v. 2.0. If a copy of the MPL was not distributed with this
file, You can obtain one at [https://mozilla.org/MPL/2.0/](https://mozilla.org/MPL/2.0/)
