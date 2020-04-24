# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

import datetime
import concurrent.futures
import sys
import re

#  These may be available in distro packages, or may need to be installed
#  with pip
import isodate
import pytz
from geopy.distance import great_circle

#  Astral v2.1 is used to calculate moon phase, sunset and sunrise times. 
#  It probably needs to be installed with pip, the distro packaged version
#  may not be up to date.  It wasn't in Fedora 31 when I wrote this.
from astral import moon
from astral import LocationInfo
from astral.sun import sun

#  Application module
import DarkskyAPIFunctions as functions

def _mapIcons(icon, flask_app=None):
	"""
	Convert NOAA and Climacell icon names to DarkSky icon names
	
	icon: the OpenWeatherMap icon name
	flask_app : an object containing a Flask application's details.  Used
                to allow us to write into the application log.
	
	Returns a DarkSky icon name

	The complete DarkSky icon set:
		clear-day.png    
		clear-night.png  
		cloudy.png  
		fog.png     
		partly-cloudy-day.png    
		partly-cloudy-night.png  
		rain.png   
		sleet.png  
		snow.png
		wind.png
	"""

	noaa_icon_list = {
		'land/day/bkn': 'partly-cloudy-day',
		'land/day/bkn/rain_showers': 'rain',
		'land/day/bkn/snow': 'snow',
		'land/day/few': 'clear-day',
		'land/day/fog': 'fog',
		'land/day/fog/wind_sct': 'fog',
		'land/day/ovc': 'cloudy',
		'land/day/rain': 'rain',
		'land/day/rain/sct': 'rain',
		'land/day/rain_showers': 'rain',
		'land/day/sct': 'partly-cloudy-day',
		'land/day/sct/rain': 'rain',
		'land/day/sct/rain_showers': 'rain',
		'land/day/sct/snow': 'snow',
		'land/day/skc': 'partly-cloudy-day',
		'land/day/snow': 'snow',
		'land/day/snow/bkn': 'snow',
		'land/day/snow/snow': 'snow',
		'land/day/tsra': 'rain',
		'land/day/wind_bkn': 'wind',
		'land/day/wind_few': 'wind',
		'land/day/wind_ovc': 'wind',
		'land/day/wind_sct': 'wind',
		'land/night/bkn': 'partly-cloudy-night',
		'land/night/bkn/rain_showers': 'rain',
		'land/night/bkn/snow': 'snow',
		'land/night/few': 'clear-night',
		'land/night/fog': 'fog',
		'land/night/fog/wind_sct': 'fog',
		'land/night/ovc': 'cloudy',
		'land/night/rain': 'rain',
		'land/night/rain/sct': 'rain',
		'land/night/rain_showers': 'rain',
		'land/night/sct': 'partly-cloudy-night',
		'land/night/sct/rain': 'rain',
		'land/night/sct/rain_showers': 'rain',
		'land/night/sct/snow': 'snow',
		'land/night/skc': 'partly-cloudy-night',
		'land/night/snow/snow': 'snow',
		'land/night/snow': 'snow',
		'land/night/snow/bkn': 'snow',
		'land/night/tsra': 'rain',
		'land/night/wind_bkn': 'wind',
		'land/night/wind_few': 'wind',
		'land/night/wind_ovc': 'wind',
		'land/night/wind_sct': 'wind',
	};

	pattern = re.compile('(?<=icons/).+?(?=,)')
	noaa_icon = re.search(pattern, icon)
	if not noaa_icon:
		pattern = re.compile('(?<=icons/).+?(?=\?)')
		noaa_icon = re.search(pattern, icon)
	if noaa_icon:
		if noaa_icon[0] in noaa_icon_list:
			return noaa_icon_list[noaa_icon[0]]
		else:
			if flask_app:
				flask_app.logger.warning('Parsed icon sucessfully but can\'t find it in the list: {}'.format(noaa_icon))
			print('Parsed icon sucessfully but can\'t find it in the list: {}'.format(noaa_icon))
	else:
		if flask_app:
			flask_app.logger.warning('Unable to parse icon URL: {}'.format(icon))
		print('Unable to parse the icon URL: {}'.format(icon))

	return ''

def dailyEpochTime(dt_str):
	'''
	Convert NOAA daily date string to UNIX epoch timestamp.  This ignores
	the time portion of the string and returns the timestamp as it would
	have been at 00:00:00 on the date specified
	'''
	d = datetime.datetime.strptime(dt_str, '%Y-%m-%dT%H:%M:%S%z')
	d = datetime.datetime.combine(datetime.date(d.year, d.month, d.day), datetime.time())
	return int(d.timestamp())

def get(latitude, longitude, useragent_string, flask_app=None):
	'''
	Use the weather data from the NOAA Weather API.
	
	Latitude
	longitude: geolocation obtained from the request URL
	useragent_string: required by NOAA to identify the caller.  See 
	                  https://www.weather.gov/documentation/services-web-api
	flask_app : an object containing a Flask application's details.  Used
                to allow us to write into the application log.
	                   
	Returns a DarkSky JSON structure that can be the output of this web
	service	
	'''
	
	#  Get the NOAA grid coordinates, timezone and URL links for this 
	#  location from their "points" service, based on the lat/long
	noaa_headers = {
		'User-Agent': useragent_string,
		'Accept': 'application/geo+json'
	}
	url = 'https://api.weather.gov/points/{},{}'.format(latitude, longitude)
	noaa_points_obj = functions.getURL(url, noaa_headers, flask_app)
	if noaa_points_obj is False:
		flask_app.logger.critical('NOAA request for location information on this latitude and longitude failed: {},{}'.format(latitude, longitude))
		return False

	#  Create the output JSON structure using the location information
	#  that came back from the service
	output = {
		'latitude': latitude,
		'longitude': longitude,
		'timezone': functions.getKeyValue(noaa_points_obj, ['properties', 'timeZone']),
		'currently': {},
		#  NOAA does not provide minutely data
		'minutely': {},
		'hourly': {},
		'daily': {},
		'alerts': [],
		'flags': {
			'sources': [],
			'units': 'us'
		}
	}

	#  Define a location for the astral functions that determine sunrise
	#  and sunset for the "daily" section of the output
	astral_location = LocationInfo('dummy_name', 'dummy_region', functions.getKeyValue(noaa_points_obj, ['properties', 'timeZone']), latitude, longitude)
	
	#  Calculate the timezone's offset from UTC in hours and add that to the
	#  output
	tz_now = datetime.datetime.now(pytz.timezone(output['timezone']))
	output['offset'] = tz_now.utcoffset().total_seconds() / 3600

	#  Using the stations URL that we got from the NOAA points lookup, find
	#  the nearest station and get its dstance away.  Add this to the output.
	url = functions.getKeyValue(noaa_points_obj, ['properties', 'observationStations']);
	noaa_stations_obj = functions.getURL(url, noaa_headers, flask_app)
	if noaa_stations_obj is False:
		flask.abort(501)
	for feature in functions.getKeyValue(noaa_stations_obj,['features']):
		miles = great_circle((latitude, longitude), (functions.getKeyValue(feature, ['geometry', 'coordinates'])[1], functions.getKeyValue(feature, ['geometry', 'coordinates'])[0])).miles
		if 'nearest-station' not in output['flags'] or miles < output['flags']['nearest-station']:
			noaa_station_url = functions.getKeyValue(feature, ['id'])
			output['flags']['nearest-station'] = round(miles, 2)

	#  Do all of the rest of the NOAA API calls simultaneously, in
	#  seperate threads, to save time
	with concurrent.futures.ThreadPoolExecutor() as executor:
		#  Get the current conditions
		url = '{}/observations/latest'.format(noaa_station_url)
		get_current = executor.submit(functions.getURL, url, noaa_headers, flask_app)

		url = functions.getKeyValue(noaa_points_obj, ['properties', 'forecastHourly']);
		get_hourly = executor.submit(functions.getURL, url, noaa_headers, flask_app)

		#  Get the grid forecast data
		url = functions.getKeyValue(noaa_points_obj, ['properties', 'forecastGridData']);
		get_griddata = executor.submit(functions.getURL, url, noaa_headers, flask_app)

		#  Get the daily forecast data
		url = functions.getKeyValue(noaa_points_obj, ['properties', 'forecast']);
		get_daily = executor.submit(functions.getURL, url, noaa_headers, flask_app)
		
		#  Get the alerts
		url = 'https://api.weather.gov/alerts?point={},{}'.format(latitude, longitude)
		get_alerts = executor.submit(functions.getURL, url, noaa_headers, flask_app)
		
		#  Get the list of all the counties in this location's state
		#  and their id codes.
		url = 'https://api.weather.gov/zones?type=county&area={}'.format(functions.getKeyValue(noaa_points_obj, ['properties', 'relativeLocation', 'properties', 'state']))
		get_counties = executor.submit(functions.getURL, url, noaa_headers, flask_app)

		#  Get the list of forecast zones in this location's state
		#  and their id codes
		url = 'https://api.weather.gov/zones?type=forecast&area={}'.format(functions.getKeyValue(noaa_points_obj, ['properties', 'relativeLocation', 'properties', 'state']))
		get_zones = executor.submit(functions.getURL, url, noaa_headers, flask_app)

		try:
			noaa_current_obj = get_current.result()
		except:
			flask_app.logger.error('Exception occurred during noaa_current_obj API call: {}'.format(sys.exc_info()[0]))
			noaa_current_obj = None
		#  If this request failed, return an empty dictionary
		if not noaa_current_obj:
			return False

		try:
			noaa_hourly_obj = get_hourly.result()
		except:
			flask_app.logger.error('Exception occurred during noaa_hourly_obj API call: {}'.format(sys.exc_info()[0]))
			noaa_hourly_obj = None
		#  If this request failed, return an empty dictionary
		if not noaa_hourly_obj:
			return False

		try:
			noaa_griddata_obj = get_griddata.result()
		except:
			flask_app.logger.error('Exception occurred during noaa_griddata_obj API call: {}'.format(sys.exc_info()[0]))
			noaa_griddata_obj = None
		#  If this request failed, return an empty dictionary
		if not noaa_griddata_obj:
			return False
			
		try:
			noaa_daily_obj = get_daily.result()
		except:
			flask_app.logger.error('Exception occurred during noaa_daily_obj API call: {}'.format(sys.exc_info()[0]))
			noaa_daily_obj = None
		#  If this request failed, return an empty dictionary
		if not noaa_daily_obj:
			return False

		try:
			noaa_alerts_obj = get_alerts.result()
		except:
			flask_app.logger.error('Exception occurred during noaa_alerts_obj API call: {}'.format(sys.exc_info()[0]))
			noaa_alerts_obj = None

		try:
			noaa_counties_obj = get_counties.result()
		except:
			flask_app.logger.error('Exception occurred during noaa_counties_obj API call: {}'.format(sys.exc_info()[0]))
			noaa_counties_obj = None

		try:
			noaa_zones_obj = get_zones.result()
		except:
			flask_app.logger.error('Exception occurred during noaa_counties_obj API call: {}'.format(sys.exc_info()[0]))
			noaa_zones_obj = None

	#  Put the county codes and their associated names into a dictionary.
	noaa_county_list = {};
	if noaa_counties_obj:
		for feature in functions.getKeyValue(noaa_counties_obj, ['features']):
			noaa_county_list[functions.getKeyValue(feature, ['properties', 'id'])] = functions.getKeyValue(feature, ['properties', 'name']);

	#  Append the list of forecast zones to the county list dictionary.
	#  Sometimes they use these in alerts instead of county codes.
	if noaa_zones_obj:
		for feature in functions.getKeyValue(noaa_zones_obj, ['features']):
			noaa_county_list[functions.getKeyValue(feature, ['properties', 'id'])] = functions.getKeyValue(feature, ['properties', 'name']);

			
	#--------------------------   C u r r e n t l y   --------------------------#

	#  Populate the output dictionary with the current observations from
	#  that station we just found
	props = functions.getKeyValue(noaa_current_obj, ['properties'])
	if props:
		output['currently'] = {
			'time': functions.getKeyValue(props, ['timestamp'], lambda x: int(functions.parseInterval(x)['start'])),
			'summary': functions.getKeyValue(props, ['textDescription'], lambda x: x.capitalize()),
			'icon': functions.getKeyValue(props, ['icon'], lambda x: _mapIcons(x, flask_app)),
			#'nearestStormDistance': None,
			'precipIntensity': functions.getKeyValue(props, ['precipitationLastHour', 'value'], lambda x: round(x / 39.37014, 2)),
			#'precipIntensityError': None,
			#'precipProbability': None,
			#'precipType': None,
			'temperature': functions.getKeyValue(props, ['temperature', 'value'], lambda x: round((x * 9 / 5) + 32, 2)),
			'apparentTemperature': functions.getKeyValue(props, ['windchill', 'value'], lambda x: round((x * 9 / 5) + 32, 2)) if functions.getKeyValue(props, ['windchill', 'value']) else functions.getKeyValue(props, ['heatIndex', 'value'], lambda x: round((x * 9 / 5) + 32, 2)),
			'dewPoint': functions.getKeyValue(props, ['dewpoint', 'value'], lambda x: round((x * 9 / 5) + 32, 2)),
			'humidity': round(100 - (5 * (props['temperature']['value'] - props['dewpoint']['value'])), 2) if functions.getKeyValue(props, ['temperature', 'value']) and functions.getKeyValue(props, ['dewpoint', 'value']) else None,
			'pressure': functions.getKeyValue(props, ['barometricpressure', 'value'], lambda x: round(x / 100, 2)),
			'windSpeed': functions.getKeyValue(props, ['windSpeed', 'value'], lambda x: round(x * 2.23694, 2)),
			'windGust': functions.getKeyValue(props, ['windGust', 'value'], lambda x: round(x * 2.23694, 2)),
			'windBearing': functions.getKeyValue(props, ['windDirection', 'value']),
			#'cloudCover': None,
			#'uvIndex': None,
			'visibility': functions.getKeyValue(props, ['visibility', 'value'], lambda x: round(x / 1609.34, 2)),
			#'ozone': None
		}

	#-----------------------------   H o u r l y   -----------------------------#
	
	#  Populate the output dictionary with the hourly data
	hours = functions.getKeyValue(noaa_hourly_obj, ['properties', 'periods']);
	if hours:
		hourly_data = []
		for hour in hours:
			#  Break out of the loop once we've got 48 hours worth
			if len(hourly_data) >= 48:
				break
			#  Include this period if its end time is greater than
			#  the current time
			if functions.parseInterval(hour['endTime'])['start'] > datetime.datetime.now().timestamp():
				hourly_data.append({
					'time': functions.parseInterval(hour['startTime'])['start'],
					'summary': functions.getKeyValue(hour, ['shortForecast'], lambda x: x.capitalize()),
					'icon': functions.getKeyValue(hour, ['icon'], lambda x: _mapIcons(x, flask_app)),
					#'pressure': None,
					#'uvIndex': None,
					#'ozone': None
				})

		#  Use NOAA's grid forecast to complete the hourly data array
		quantities = functions.getKeyValue(noaa_griddata_obj, ['properties', 'quantitativePrecipitation', 'values']);
		if quantities:
			for quantity in quantities:
				interval = functions.parseInterval(quantity['validTime'])
				hours = (interval['end'] - interval['start']) / 3600
				perhour = round(quantity['value'] / 25.4 / hours, 2)
				for i in range(len(hourly_data)):
					if hourly_data[i]['time'] >= interval['start'] and hourly_data[i]['time'] < interval['end']:
						hourly_data[i]['precipIntensity'] = perhour
					if hourly_data[i]['time'] > interval['end']:
						break

		snowamounts = functions.getKeyValue(noaa_griddata_obj, ['properties', 'snowfallAmount', 'values']);
		if snowamounts:
			for snow in snowamounts:
				interval = functions.parseInterval(snow['validTime'])
				hours = (interval['end'] - interval['start']) / 3600
				perhour = round(snow['value'] / 25.4 / hours, 2)
				for i in range(len(hourly_data)):
					if hourly_data[i]['time'] >= interval['start'] and hourly_data[i]['time'] < interval['end']:
						if 'precipIntensity' in hourly_data[i]:
							if perhour > hourly_data[i]['precipIntensity']:
								hourly_data[i]['precipIntensity'] = perhour
						else:
							hourly_data[i]['precipIntensity'] = perhour
					if hourly_data[i]['time'] > interval['end']:
						break

		probabilities = functions.getKeyValue(noaa_griddata_obj, ['properties', 'probabilityOfPrecipitation', 'values']);
		if probabilities:
			for probability in probabilities:
				interval = functions.parseInterval(probability['validTime'])
				for i in range(len(hourly_data)):
					if hourly_data[i]['time'] >= interval['start'] and hourly_data[i]['time'] < interval['end']:
						hourly_data[i]['precipProbability'] = round(probability['value'] / 100, 2)
					if hourly_data[i]['time'] > interval['end']:
						break

						
		temperatures = functions.getKeyValue(noaa_griddata_obj, ['properties', 'temperature', 'values']);
		if temperatures:
			for temp in temperatures:
				interval = functions.parseInterval(temp['validTime'])
				for i in range(len(hourly_data)):
					if hourly_data[i]['time'] >= interval['start'] and hourly_data[i]['time'] < interval['end']:
						hourly_data[i]['temperature'] = round((temp['value'] * 9 / 5) + 32, 2)
					if hourly_data[i]['time'] > interval['end']:
						break
						
		apparents = functions.getKeyValue(noaa_griddata_obj, ['properties', 'apparentTemperature', 'values']);
		if apparents:
			for apparent in apparents:
				interval = functions.parseInterval(apparent['validTime'])
				for i in range(len(hourly_data)):
					if hourly_data[i]['time'] >= interval['start'] and hourly_data[i]['time'] < interval['end']:
						hourly_data[i]['apparentTemperature'] = round((apparent['value'] * 9 / 5) + 32, 2)
					if hourly_data[i]['time'] > interval['end']:
						break

		dewpoints = functions.getKeyValue(noaa_griddata_obj, ['properties', 'dewpoint', 'values']);
		if dewpoints:
			for dewpoint in dewpoints:
				interval = functions.parseInterval(dewpoint['validTime'])
				for i in range(len(hourly_data)):
					if hourly_data[i]['time'] >= interval['start'] and hourly_data[i]['time'] < interval['end']:
						hourly_data[i]['dewpoint'] = round((dewpoint['value'] * 9 / 5) + 32, 2)
					if hourly_data[i]['time'] > interval['end']:
						break
						
		humidities = functions.getKeyValue(noaa_griddata_obj, ['properties', 'relativeHumidity', 'values']);
		if humidities:
			for humidity in humidities:
				interval = functions.parseInterval(humidity['validTime'])
				for i in range(len(hourly_data)):
					if hourly_data[i]['time'] >= interval['start'] and hourly_data[i]['time'] < interval['end']:
						hourly_data[i]['humdity'] = round(humidity['value'] / 100, 2)
					if hourly_data[i]['time'] > interval['end']:
						break
						
		windspeeds = functions.getKeyValue(noaa_griddata_obj, ['properties', 'windSpeed', 'values']);
		if windspeeds:
			for speed in windspeeds:
				interval = functions.parseInterval(speed['validTime'])
				for i in range(len(hourly_data)):
					if hourly_data[i]['time'] >= interval['start'] and hourly_data[i]['time'] < interval['end']:
						hourly_data[i]['windSpeed'] = round(speed['value'] * 2.23694, 2)
					if hourly_data[i]['time'] > interval['end']:
						break

		windgusts = functions.getKeyValue(noaa_griddata_obj, ['properties', 'windGust', 'values']);
		if windgusts:
			for gust in windgusts:
				interval = functions.parseInterval(gust['validTime'])
				for i in range(len(hourly_data)):
					if hourly_data[i]['time'] >= interval['start'] and hourly_data[i]['time'] < interval['end']:
						hourly_data[i]['windGust'] = round(gust['value'] * 2.23694, 2)
					if hourly_data[i]['time'] > interval['end']:
						break

		winddirections = functions.getKeyValue(noaa_griddata_obj, ['properties', 'windDirection', 'values']);
		if winddirections:
			for direction in winddirections:
				interval = functions.parseInterval(direction['validTime'])
				for i in range(len(hourly_data)):
					if hourly_data[i]['time'] >= interval['start'] and hourly_data[i]['time'] < interval['end']:
						hourly_data[i]['windBearing'] = round(direction['value'])
					if hourly_data[i]['time'] > interval['end']:
						break

		skycovers = functions.getKeyValue(noaa_griddata_obj, ['properties', 'skyCover', 'values']);
		if skycovers:
			for skycover in skycovers:
				interval = functions.parseInterval(skycover['validTime'])
				for i in range(len(hourly_data)):
					if hourly_data[i]['time'] >= interval['start'] and hourly_data[i]['time'] < interval['end']:
						hourly_data[i]['cloudCover'] = round(skycover['value'] / 100, 2)
					if hourly_data[i]['time'] > interval['end']:
						break


		visibilities = functions.getKeyValue(noaa_griddata_obj, ['properties', 'visibility', 'values']);
		if visibilities:
			for visibility in visibilities:
				interval = functions.parseInterval(visibility['validTime'])
				for i in range(len(hourly_data)):
					if hourly_data[i]['time'] >= interval['start'] and hourly_data[i]['time'] < interval['end']:
						hourly_data[i]['visibility'] = round(visibility['value'] / 1609.34, 2)
					if hourly_data[i]['time'] > interval['end']:
						break

		#  Add the hourly data array to the output dictionary
		if len(hourly_data) > 0:
			output['hourly'] = {
				'summary': hourly_data[0]['summary'],
				'icon': hourly_data[0]['icon'],
				'data': hourly_data
			}
			
	#------------------------------   D a i l y   ------------------------------#
	
	#  Populate the output dictionary with the hourly data.  NOAA
	#  provides seperate daytime and nighttime forecasts for each day,
	#  we focus on the daytime forecasts
	daily_data = []
	periods = functions.getKeyValue(noaa_daily_obj, ['properties', 'periods'])
	
	#  Calculate UNIX Epoch timestamp for the first day in the daily
	#  forecast array
	d = datetime.datetime.now()
	d = datetime.datetime.combine(datetime.date(d.year, d.month, d.day), datetime.time())
	d = pytz.timezone(functions.getKeyValue(noaa_points_obj, ['properties', 'timeZone'])).localize(d)
	timestamp = int(d.timestamp())
	
	#  Build an array to hold the daily forecasts
	for i in range(len(periods)):
		if dailyEpochTime(periods[i]['startTime']) == timestamp:
			the_sun = sun(astral_location.observer, date=datetime.datetime.utcfromtimestamp(timestamp))
			daily_data.append({
				'time': timestamp,
				'summary': functions.getKeyValue(periods, [i, 'shortForecast']),
				'icon': functions.getKeyValue(periods, [i, 'icon'], lambda x: _mapIcons(x, flask_app)),
				'sunriseTime': round(the_sun['sunrise'].timestamp()),
				'sunsetTime': round(the_sun['sunset'].timestamp()),
				'moonPhase': round(moon.phase(datetime.datetime.utcfromtimestamp(timestamp)) / 27.99, 2),
				#'precipIntensity', None,
				#'precipIntensityMax',
				#'precipIntensityMaxTiome',
				'precipProbability': None,
				#'precipType': None,
				'temperatureHigh': None,
				'temperatureHighTime': None,
				'temperatureLow': None,
				'temperatureLowTime': None,
				'apparentTemperatureHigh': None,
				'apparentTemperatureHighTime': None,
				'apparentTemperatureLow': None,
				'apparentTemperatureLowTime': None,
				'dewPoint': None,
				'humidity': None,
				#'pressure': None,
				'windSpeed': None,
				'windGust': None,
				'windGustTime': None,
				'windBearing': None,
				'cloudCover': None,
				#'uvIndex': None,
				#'uvIndexTime', None,
				'visibility': None,
				#'ozone': None,
				'temperatureMin': None,
				'temperatureMinTime': None,
				'temperatureMax': None,
				'temperatureMaxTime': None,
				'apparentTemperatureMin': None,
				'apparentTemperatureMinTime': None,
				'apparentTemperatureMax': None,
				'apparentTemperatureMaxTime': None
			})
			timestamp = timestamp + (3600 * 24)
			
	#  Fill in remaining daily data using the NOAA gridpoint forecast query
	props = functions.getKeyValue(noaa_griddata_obj, ['properties'])
	for i in range(len(daily_data)):
		start = daily_data[i]['time']
		end = start + (3600 * 24)

		#  Scan through each day's temperature data and get the highs and lows
		for value in props['temperature']['values']:
			timestamp = functions.getKeyValue(value, ['validTime'], lambda x: functions.parseInterval(x)['start'])
			if timestamp >= end:
				break;
			temp = functions.getKeyValue(value, ['value']);
			if temp != None:
				temp = round((temp * 9 / 5) + 32, 2)
				if timestamp >= start and timestamp < end:
					if not daily_data[i]['temperatureHigh'] or temp > daily_data[i]['temperatureHigh']:
						daily_data[i]['temperatureHigh'] = temp
						daily_data[i]['temperatureHighTime'] = timestamp
						daily_data[i]['temperatureMax'] = temp
						daily_data[i]['temperatureMaxTime'] = timestamp
					if not daily_data[i]['temperatureLow'] or temp < daily_data[i]['temperatureLow']:
						daily_data[i]['temperatureLow'] = temp
						daily_data[i]['temperatureLowTime'] = timestamp
						daily_data[i]['temperatureMin'] = temp
						daily_data[i]['temperatureMinTime'] = timestamp
		for value in props['apparentTemperature']['values']:
			timestamp = functions.getKeyValue(value, ['validTime'], lambda x: functions.parseInterval(x)['start'])
			if timestamp >= end:
				break;
			temp = functions.getKeyValue(value, ['value']);
			if temp != None:
				temp = round((temp * 9 / 5) + 32, 2)
				if timestamp >= start and timestamp < end:
					if not daily_data[i]['apparentTemperatureHigh'] or temp > daily_data[i]['apparentTemperatureHigh']:
						daily_data[i]['apparentTemperatureHigh'] = temp
						daily_data[i]['apparentTemperatureHighTime'] = timestamp
						daily_data[i]['apparentTemperatureMax'] = temp
						daily_data[i]['apparentTemperatureMaxTime'] = timestamp
					if not daily_data[i]['apparentTemperatureLow'] or temp < daily_data[i]['apparentTemperatureLow']:
						daily_data[i]['apparentTemperatureLow'] = temp
						daily_data[i]['apparentTemperatureLowTime'] = timestamp
						daily_data[i]['apparentTemperatureMin'] = temp
						daily_data[i]['apparentTemperatureMinTime'] = timestamp
		
		#  Calculate the average dewpoint temperature for the day
		total = 0;
		total_hours = 0;
		for value in props['dewpoint']['values']:
			interval = functions.parseInterval(functions.getKeyValue(value, ['validTime']))
			if interval['end'] > start and interval['start'] <= end:
				if interval['start'] < start:
					interval['start'] = start
				if interval['end'] > end:
					interval['end'] = end
				hours = (interval['end'] - interval['start']) / 3600;
				dp = functions.getKeyValue(value, ['value'])
				if dp != None:
					total = total + (dp * hours);
					total_hours = total_hours + hours;
		if total_hours > 0:
			daily_data[i]['dewPoint'] = round((total / total_hours * 9 / 5) + 32, 2);

		#  Calculate the average humidity for the day
		total = 0;
		total_hours = 0;
		for value in props['relativeHumidity']['values']:
			interval = functions.parseInterval(functions.getKeyValue(value, ['validTime']))
			if interval['end'] > start and interval['start'] <= end:
				if interval['start'] < start:
					interval['start'] = start
				if interval['end'] > end:
					interval['end'] = end
				hours = (interval['end'] - interval['start']) / 3600;
				hum = functions.getKeyValue(value, ['value'])
				if hum != None:
					total = total + (hum * hours);
					total_hours = total_hours + hours;
		if total_hours > 0:
			daily_data[i]['humidity'] = round(total / total_hours / 100, 2);

		#  Calculate the average cloudCover percentage for the day
		total = 0;
		total_hours = 0;
		for value in props['skyCover']['values']:
			interval = functions.parseInterval(functions.getKeyValue(value, ['validTime']))
			if interval['end'] > start and interval['start'] <= end:
				if interval['start'] < start:
					interval['start'] = start
				if interval['end'] > end:
					interval['end'] = end
				hours = (interval['end'] - interval['start']) / 3600;
				clo = functions.getKeyValue(value, ['value'])
				if clo != None:
					total = total + (clo * hours);
					total_hours = total_hours + hours;
		if total_hours > 0:
			daily_data[i]['cloudCover'] = round(total / total_hours / 100, 2);

		#  Calculate the average windDirection for the day
		total = 0;
		total_hours = 0;
		for value in props['windDirection']['values']:
			interval = functions.parseInterval(functions.getKeyValue(value, ['validTime']))
			if interval['end'] > start and interval['start'] <= end:
				if interval['start'] < start:
					interval['start'] = start
				if interval['end'] > end:
					interval['end'] = end
				hours = (interval['end'] - interval['start']) / 3600;
				dir = functions.getKeyValue(value, ['value'])
				if dir != None:
					total = total + (dir * hours);
					total_hours = total_hours + hours;
		if total_hours > 0:
			daily_data[i]['windBearing'] = round(total / total_hours);

		#  Calculate the average windSpeed for the day
		total = 0;
		total_hours = 0;
		for value in props['windSpeed']['values']:
			interval = functions.parseInterval(functions.getKeyValue(value, ['validTime']))
			if interval['end'] > start and interval['start'] <= end:
				if interval['start'] < start:
					interval['start'] = start
				if interval['end'] > end:
					interval['end'] = end
				hours = (interval['end'] - interval['start']) / 3600;
				spe = functions.getKeyValue(value, ['value'])
				if spe != None:
					total = total + (spe * hours);
					total_hours = total_hours + hours;
				total_hours = total_hours + hours;
		if total_hours > 0:
			daily_data[i]['windSpeed'] = round(total / total_hours * 2.23694, 2);

		#  Calculate the average precipitation probability for the day
		total = 0;
		total_hours = 0;
		for value in props['probabilityOfPrecipitation']['values']:
			interval = functions.parseInterval(functions.getKeyValue(value, ['validTime']))
			if interval['end'] > start and interval['start'] <= end:
				if interval['start'] < start:
					interval['start'] = start
				if interval['end'] > end:
					interval['end'] = end
				hours = (interval['end'] - interval['start']) / 3600;
				pro = functions.getKeyValue(value, ['value'])
				if pro != None:
					total = total + (pro * hours);
					total_hours = total_hours + hours;
		if total_hours > 0:
			daily_data[i]['precipProbability'] = round(total / total_hours / 100, 2);

		#  Calculate the average visibility for the day (remember that
		#  NOAA only provides this data for the first 24 hours (2 days.)
		total = 0;
		total_hours = 0;
		for value in props['visibility']['values']:
			interval = functions.parseInterval(functions.getKeyValue(value, ['validTime']))
			if interval['end'] > start and interval['start'] <= end:
				if interval['start'] < start:
					interval['start'] = start
				if interval['end'] > end:
					interval['end'] = end
				hours = (interval['end'] - interval['start']) / 3600;
				vis = functions.getKeyValue(value, ['value'])
				if vis != None:
					total = total + (vis * hours);
					total_hours = total_hours + hours;
		if total_hours > 0:
			daily_data[i]['visibility'] = round(total / total_hours / 1609.34, 2);

		#  Get the maximum windGust for the day and its associated timestamp
		for prop in props['windGust']['values']:
			timestamp = functions.getKeyValue(prop, ['validTime'], lambda x: functions.parseInterval(x)['start']);
			if timestamp >= end:
				break
			value = functions.getKeyValue(prop, ['value'])
			if value != None:
				value = round(value * 2.23694, 2)
				if timestamp >= start and timestamp < end:
					if not daily_data[i]['windGust'] or value > daily_data[i]['windGust']:
						daily_data[i]['windGust'] = value
						daily_data[i]['windGustTime'] = timestamp
				
	#  Add the daily data array to the output dictionary
	if len(daily_data) > 0:
		output['daily'] = {
			'summary': daily_data[0]['summary'],
			'icon': daily_data[0]['icon'],
			'data': daily_data
		}
				
	#-----------------------------   A l e r t s   -----------------------------#

	#  Popluate the output dictionary with any alerts that pertain to
	#  this location.  If there are none, delete the "alerts" key from
	#  the output dictionary.
	if noaa_alerts_obj:
		alerts = functions.getKeyValue(noaa_alerts_obj, ['features'])
		if alerts:
			alert_data = []
			for alert in alerts:
				props = functions.getKeyValue(alert, ['properties'])
				#  Don't include expired alerts
				if functions.getKeyValue(props, ['expires'], lambda x: functions.parseInterval(x)['start']) > datetime.datetime.now().timestamp():
					#  Use the noaa_county_list dictionary we built at the
					#  beginning to convert the county IDs listed in the
					#  alert to county names.
					regions = []
					for county_id in functions.getKeyValue(props, ['geocode', 'UGC']):
						regions.append(noaa_county_list[county_id])
					#  Populate the alert data array with the data from NOAA	
					alert_data.append({
						'title': functions.getKeyValue(props, ['event']),
						'regions': regions,
						'severity': functions.getKeyValue(props, ['severity']),
						'time': functions.getKeyValue(props, ['onset'],  lambda x: functions.parseInterval(x)['start']),
						'expires': functions.getKeyValue(props, ['expires'],  lambda x: functions.parseInterval(x)['start']),
						'description': functions.getKeyValue(props, ['description'], lambda x: re.sub(r'\s+', ' ', x)),
						'url': functions.getKeyValue(props,['@id'])
					})
			
			#  Add the alerts data array to the output dictionary	
			output['alerts'] = alert_data
	
	#  Flag the output as including data from NOAA	
	output['flags']['sources'] = 'noaa',

	return output
