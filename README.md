A weather forecasting web service that provides the same information that has been available from the [DarkSky API](https://darksky.net/dev).  DarkSky has recently been acquired by Apple and has announced that their API will continue to be available for currently registered users until June 2021, with no new registrations being accepted between now and then.  When that service disappears I'll need something else to support the weather widgets that I built for the video dashboard in my home.

This Python Flask-based web service uses free weather data from NOAA and Climacell and returns that data in the same JSON format that the DarkSky API used.  This web service also uses the same request URL format that DarkSky used:

     http://<hostname.domainname>:<port>/forecast/<Climacell-API-key>/<latitude>,<longitude>

The code is modularized so that other weather services could be added or removed in the future.  A design assumption is that the [NOAA Weather API](https://www.weather.gov/documentation/services-web-api) web service should continue to exist as-is for a long period of time.  The application is designed to use that service to use that service to build as complete a response as possible, one that could stand on its own, and then to replace/extend that response using additional service(s) like Climacell.  The [Climacell MicroWeather API](https://www.climacell.co/weather-api/) service is consider significantly less stable than NOAA, much more likely to change or disappear in the future.

The [NOAA Weather API](https://www.weather.gov/documentation/services-web-api) is free to use.  No registration or API key is necessary.  They do ask that the UserAgent header be set on each request so that they have some means to contact someone if there are issues.  There's a variable very near the top of the darksky-api.py file where a string can be set for this purpose.  See the "Authorization" paragraph on the [NOAA Weather API Web Service page](https://www.weather.gov/documentation/services-web-api) for a description of what NOAA is looking for here.  I have not found any information on rate limits for these services but they only update once an hour so there's no point in hammering away at them.

The [Climacell MicroWeather API](https://www.climacell.co/weather-api/) is a paid service but there is a free option for developers that has limited capabilities and usage limits.  All they ask for is a name and e-mail address and they instantaneously send out an e-mail containing an API key.  A free account gets 1000 API calls per day.  This script makes four API calls every time it runs.  That means the script can run 250 times per or once every 5 minutes 46 seconds.  My dashboard has been doing one call to the DarkSky API every 30 minutes.  That would translate into 192 Climacall API calls per day.

There are some gaps in the data that NOAA/Climacell can provide versus DarkSky.  These are marked in the source code, in NOAAWeatherAPI.py and ClimacellWeatherAPI.py.  I summary:

- There is no "nearestStormDistance" and "nearestStormBearing" data.
- There is no "precipProbability" data in the "currently" section or "minutely" forecasts section.
- There is no "precipType" data in the "daily" forecasts section.
- There is no "uvIndex" data.
For more information on these APIs, see:

- [DarkSky's API](https://darksky.net/dev/docs)
- [NOAA's Weather API Web Service](https://www.weather.gov/documentation/services-web-api)
- [Climacell's MicroWeather API](https://www.climacell.co/weather-api/docs/)

###Installation

This script is written for Python version 3.  It uses the Astral module whose RPM package is out of date on Fedora 31 where I work.  I also use the timezonefinder module which is not packaged for Fedora.  I therefore run this service in a Python virtual environment where I can install modules at will without affecting other applications on my system.  Here's the one-time setup procedure I used to create that virtual environment, with the necessary modules installed, in the home directory of my regular userid:

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

The web service will now be available at this URL:

    http://localhost:5000/forecast/<your-Climacell-API-key>/<latitude>,<longitude>

When I'm finished:

    Ctrl-C to terminate flask
    (darksky-api-venv) $ deactivate

The application will log messages into a darksky-api.log file in the current directory.  It will also write some messages to the development console.

The Flask documentation discusses the many options for deploying a Flask application in production.  I use the uwsgi service on CentOS 8.  This repository include the ini configuration files  that I use for this purpose.

###License

This Source Code Form is subject to the terms of the Mozilla Public
License, v. 2.0. If a copy of the MPL was not distributed with this
file, You can obtain one at [https://mozilla.org/MPL/2.0/](https://mozilla.org/MPL/2.0/)
