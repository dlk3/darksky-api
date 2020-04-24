This project provides a replacement for the DarkSky weather forecasting
API.  I use this API to feed weather widgets on my family's video
dashboard.  DarkSky has recently been acquired by Apple and has announced
that their API will continue to be available for currently registered users
until June 2021, with no new registrations being accepted between now and
then.  I'm assuming that this means the API will dissappear after June
2021.

Rather than rewrite my dashboard, I decided to create an "adapter" script
that could provide the same data as the DarkSky API does, in the same JSON
format that DarkSky uses, using other weather APIs as its data sources.
I first tried writing this as a PHP web service. fetching and formatting
the weather data inline with the processing of the dashboard page.  This
proved to be pretty slow.  I then moved to the current approach which is
to run a Python script on a loop, writing the weather forecast in DarkSky
JSON format to a file.  My dashboard page can then read in the JSON data
from this file whenever it needs it.  This is very fast.  

This script operates on a 5 minute loop.  Neither of the web services I 
use update their weather data that quickly, but I wanted to make sure that
I pick up on any weather alerts in a reasonable amount of time.  NOAA
publishes alerts via their web service immediately when they are issued.
A five minute loop means that my script makes 288 calls to the 
OpenWeatherMap API per day, which is well within the 1000 calls per day
limit that OpenWeatherMap imposes on free accounts using their One
Call API.  I have not found any mention of a call limit for the NOAA
Weather API.

I give the data from the OpenWeatherMap API priority in this script.  If
OpenWeatherMap provides the data elements that the DarkSky API format
requires, then I use it.  Whatever is left is filled in using data from
the NOAA Weather API.  Not all of the data elements that DarkSky provided
are available from these other services.  Fortunately for me, I never used
any of the missing elements in my dashboard.  Those missing elements
include:
	
- "nearestStormDistance" and "nearestStormBearing",

- "ozone" data,

- the entire "minutely" section of the DarkSky API output,

  This section provided data on precipitation probability, intensity, and
  type minute-by-minute for the next 60 minutes.  
  
  While they aren't available on a aminute-by-minute basis, precipitation
  probability, intensity and type are available from OpenWeatherMap and
  NOAA APIs for the "hourly" and "daily" parts of the DarkSky API output.

Use these links for additional information on the APIs involved here:

- [DarkSky's API](https://darksky.net/dev/docs)
- [OpenWeatherMap's One Call API](https://openweathermap.org/api/one-call-api)
- [NOAA's Weather API Web Service](https://www.weather.gov/documentation/services-web-api)

###Installation

I developed this script on Fedora 31 where Python 3.7.6 is the default and
there are repository packages for all of the modules that I used.  I run
this script on CentOS 7 where Python 2.7.5 is the default but Python
3.6.8 is available as a packaged option.  Unfortunatly, not all of the
modules that I used are available as repository packages for Python 3.6
on CentOS 7.  So I have chosen to run this script in a virtual Python 3.6
environment where I've used `pip` to install the modules that I need.
Here's the one-time setup procedure I used to create that virtual 
environment, with the necessary modules installed, in the home directory
of my regular userid:

    $ sudo yum install python36 python36-virtualenv
    $ python3.6 -m venv weather-api-venv
    $ source weather-api-venv/bin/activate
    (weather-api-venv) $ pip install --upgrade pip
    (weather-api-venv) $ pip install requests geopy isodate pytz
    (weather-api-venv) $ deactivate

I put my `darksky-api` script in the `/usr/local/bin` directory.

I put my `darksky-api.conf` file in my home directory and customized it 
with my API keys and my location's latitude and longitude.

Now I can run my script with this command line:

    $ PATH=~/weather-api-venv/bin:$PATH /usr/local/bin/darksky-api

If, at some point in the future, I want to remove the virtual environment,
that's as simple as doing: `rm -fr ~/weather-api-venv`

###License

This Source Code Form is subject to the terms of the Mozilla Public
License, v. 2.0. If a copy of the MPL was not distributed with this
file, You can obtain one at https://mozilla.org/MPL/2.0/.
