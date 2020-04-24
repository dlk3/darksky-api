# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

'''
This script provides a Python Flask web service which emulates the
DarkSky weather API, returning a JSON object that matches the output of
the DarkSky API.  This script uses free weather data web services
provided by NOAA and Climacell as a replacement for DarkSky.

See the README.md for additional details
'''

#  See https://www.weather.gov/documentation/services-web-api for info
#  on what NOAA wants passed through in the UserAgent header:
noaa_useragent_string = '(David King, dave@daveking.com)'

import datetime
import json
import os

#  Flask modules
import flask
import logging
from logging.config import dictConfig

#  Application modules
import NOAAWeatherAPI
import ClimacellWeatherAPI

#  Configure application logging
dictConfig({
    'version': 1,
    'formatters': {'default': {
        'format': '[%(asctime)s] %(levelname)s in %(module)s: %(message)s',
    }},
    'handlers': {__name__ + '_log': {
        'class': 'logging.handlers.RotatingFileHandler',
        'filename': 'darksky-api.log',
        'maxBytes': 107374182400, 	# 100MiB
        'backupCount': 1,
        'formatter': 'default'
    }},
    'root': {
        'level': 'INFO',
        'handlers': [__name__ + '_log']
    }
})

#  Initialize the app and set its name
app = flask.Flask(__name__)

#  Define the route and the routehandler function
@app.route('/forecast/<apikey>/<geolocation>')
def forecast(apikey, geolocation):
	#  We will log the time it takes to process each request
	start_timestamp = datetime.datetime.now().timestamp()
	
	#  Parse and verify the latitude,longitude we received
	gsplit = geolocation.split(',')
	if len(gsplit) != 2:
		app.logger.error('Unable to split the request latitude,longitude')
		return 'URL must include a valid latitude,longitude', 400
	try:
		latitude = float(gsplit[0])
		longitude = float(gsplit[1])
	except:
		app.logger.error('Latitude,longitude are not valid floating point numbers')
		return 'URL must include a valid latitude,longitude', 400
	if latitude > 65 or latitude < 19:
		app.logger.error('Request latitude, {}, was not between 19 and 65'.format(latitude))
		return 'URL must include a valid latitude,longitude for a location in the USA', 400
	if longitude > -67 or longitude < -162:
		app.logger.error('Request longitude, {}, was not between -162 and -67'.format(longitude))
		return 'URL must include a valid latitude,longitude for a location in the USA', 400
		
	#  Get the weather information that NOAA is able to provide
	output = NOAAWeatherAPI.get(latitude, longitude, noaa_useragent_string, flask_app=app)
	
	#  Enhance the output with weather information from climacell
	output = ClimacellWeatherAPI.get(latitude, longitude, apikey, input_dictionary=output, flask_app=app)
	
	#  Keep a cached copy of the output for those occasions when we are
	#  completely unable to read any of the backend data services
	cached_copy_filename = 'darksky-api.cached_output'
	if output:
		#  If there are no alerts in the output, remove the alerts key
		if 'alerts' in output:
			if len(output['alerts']) == 0:
				del output['alerts']
		#  Cache a copy of the output
		with open(cached_copy_filename, 'w') as f:
			json.dump(output, f)
	elif os.path.exists(cached_copy_filename):
		#  We got no output from the backend data services, read in the
		#  cached file, if it exists
		with open(cached_copy_filename, 'r') as f:
			output = json.load(f)
	else:
		#  When all else fails, return nothing
		app.logger.warning('Failed to obtain any weather data.  Sending error message with status code = 502,')
		elapsed_time = round(datetime.datetime.now().timestamp() - start_timestamp)
		app.logger.warning('Processed request in {} seconds'.format(elapsed_time))
		return 'Failed to obtain any weather data.', 502
	
	#  Send the output response
	output = json.dumps(output, indent=4)
	r = flask.Response(output)
	elapsed_time = round(datetime.datetime.now().timestamp() - start_timestamp)
	r.headers['X-Response-Time'] = elapsed_time
	app.logger.info('Processed request in {} seconds'.format(elapsed_time))
	r.headers['Content-Type'] = 'application/json'
	return r
