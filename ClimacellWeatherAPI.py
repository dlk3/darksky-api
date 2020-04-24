# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

import datetime
import concurrent.futures
import sys

#  These may be available in distro packages, or may need to be
#  installed with pip
import isodate
import pytz

#  Astral v2.1 is used to calculate moon phase.  It probably needs to be
#  installed with pip, the distro packaged version may not be up to date.
#  It wasn't in Fedora 31 when I wrote this.
from astral import moon

#  Climacell doesn't provide the timezone.  TimezoneFinder returns a
#  timezone text string when it's fed a latitude and longitude.  It
#  probably needs to be installed with pip.
from timezonefinder import TimezoneFinder

#  Application module
import DarkskyAPIFunctions as functions

def _mapIcons(icon, flask_app=None):
	"""
	Convert Climacell weather condition labels to DarkSky icon names
	
	icon: the Climacell weather condition label
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

	climacell_icon_list = {
		'freezing_rain_heavy': 'sleet', 
		'freezing_rain': 'sleet', 
		'freezing_rain_light': 'sleet', 
		'freezing_drizzle': 'sleet', 
		'ice_pellets_heavy': 'sleet', 
		'ice_pellets': 'sleet', 
		'ice_pellets_light': 'sleet', 
		'snow_heavy': 'snow', 
		'snow': 'snow', 
		'snow_light': 'snow', 
		'flurries': 'snow', 
		'tstorm': 'rain', 
		'rain_heavy': 'rain', 
		'rain': 'rain', 
		'rain_light': 'rain', 
		'drizzle': 'rain', 
		'fog_light': 'fog', 
		'fog': 'fog', 
		'cloudy': 'cloudy', 
		'mostly_cloudy': 'cloudy',
		'partly_cloudy': 'partly-cloudy-day', 
		'mostly_clear': 'clear-day', 
		'clear': 'clear-day'
	};

	if icon in climacell_icon_list:
		return climacell_icon_list[icon]
	else:
		if flask_app:
			flask_app.logger.warning('Can\'t find the icon in the Climacell list: {}'.format(noaa_icon))
		print('Can\'t find the icon in the Climacell list: {}'.format(noaa_icon))

	return ''

def _mapClimacellWeatherCode(code):
	'''
	Translate Climacell's weather_code values into short text phrases
	 
	code: a Climacell weather_code
	
	Returns a string
	'''
	weather_codes = {
		'freezing_rain_heavy': 'Heavt Freezing Rain', 
		'freezing_rain': 'Freezing Rain', 
		'freezing_rain_light': 'Light Freezing Rain', 
		'freezing_drizzle': 'Freezing Drizzle', 
		'ice_pellets_heavy': 'Heavy Sleet', 
		'ice_pellets': 'Sleet', 
		'ice_pellets_light': 'Light Sleet', 
		'snow_heavy': 'Heavy Snow', 
		'snow': 'Snow', 
		'snow_light': 'Light Snow', 
		'flurries': 'Snow Flurries', 
		'tstorm': 'Thundestorms', 
		'rain_heavy': 'Heavy Rain', 
		'rain': 'Rain', 
		'rain_light': 'Light Rain', 
		'drizzle': 'Drizzle', 
		'fog_light': 'Light Fog', 
		'fog': 'Fog', 
		'cloudy': 'Cloudy', 
		'mostly_cloudy': 'Mostly Cloudy',
		'partly_cloudy': 'Partly Cloudy', 
		'mostly_clear': 'Mostly Clear', 
		'clear': 'Clear'
	}
	
	if code:
		if code in weather_codes:
			return weather_codes[code]
		else:
			flask_app.logger.warning('Could not find "{}" in the Climacell weather codes list'.format(code))
			print('Could not find "{}" in the Climacell weather codes list'.format(code))
	return ''

def _epochTime(dt_str):
	'''
	Convert Climacell date string to UNIX epoch timestamp
	'''
	return int(datetime.datetime.strptime(dt_str, '%Y-%m-%dT%H:%M:%S.%fZ').replace(tzinfo=datetime.timezone.utc).timestamp())
	
def _dailyEpochTime(dt_str):
	'''
	Convert Climacell daily date string to UNIX epoch timestamp
	'''
	return int(datetime.datetime.combine(datetime.datetime.strptime(dt_str, '%Y-%m-%d'), datetime.time()).timestamp())	
def get(latitude, longitude, apikey, input_dictionary=None, flask_app=None):
	'''
	Use the weather data from the Climacell API.  This data will overwrite
	and extend what we got from NOAA.
	
	Latitude
	longitude: geolocation obtained from the request URL
	apikey: the user's Climacell API key from a free account (or paid)
	input_dictionary: a DarkSky JSON structure created by another routine
	                  in this script like the getNOAAWeatherInfo rountine,
	                  for example.  This is optional.  If a JSON structure
	                  isn't passed through, then one will be created from
	                  scratch.
	flask_app : an object containing a Flask application's details.  Used
                to allow us to write into the application log.
	                   
	Returns a DarkSky JSON structure that can be the output of this web
	service
	'''

	cc_headers = {
		'Accept': 'application/json',
		'apikey': apikey
	}
	
	#  Do all of the Climacell API calls simultaneously, in seperate
	#  threads, to save time
	with concurrent.futures.ThreadPoolExecutor() as executor:
		url = 'https://api.climacell.co/v3/weather/realtime?lat={}&lon={}&unit_system=us&fields=precipitation,precipitation%3Ain%2Fhr,precipitation_type,temp,feels_like,dewpoint,wind_speed,wind_gust,baro_pressure%3AhPa,visibility,humidity,wind_direction,cloud_cover,weather_code,o3'.format(latitude, longitude)
		get_current = executor.submit(functions.getURL, url, cc_headers, flask_app)
	
		minutely_starttime = (datetime.datetime.utcnow() + datetime.timedelta(minutes=1)).strftime('%Y-%m-%dT%H:%M:%S.000Z')
		minutely_endtime = (datetime.datetime.utcnow() + datetime.timedelta(minutes=61)).strftime('%Y-%m-%dT%H:%M:%S.000Z')
		url = 'https://api.climacell.co/v3/weather/nowcast?lat={}&lon={}&unit_system=us&fields=precipitation%3Ain%2Fhr,precipitation_type&start_time={}&end_time={}&timestep=1'.format(latitude, longitude, minutely_starttime, minutely_endtime)
		get_minutely = executor.submit(functions.getURL, url, cc_headers, flask_app)
	
		url = 'https://api.climacell.co/v3/weather/forecast/hourly?lat={}&lon={}&unit_system=us&fields=precipitation,precipitation%3Ain%2Fhr,precipitation_type,precipitation_probability,temp,feels_like,dewpoint,wind_speed,wind_gust,baro_pressure%3AhPa,visibility,humidity,wind_direction,cloud_cover,weather_code,o3&start_time=now'.format(latitude, longitude)
		get_hourly = executor.submit(functions.getURL, url, cc_headers, flask_app)
	
		url = 'https://api.climacell.co/v3/weather/forecast/daily?lat={}&lon={}&start_time=now&unit_system=us&fields=temp,feels_like,wind_speed,wind_direction,baro_pressure%3AhPa,precipitation,precipitation%3Ain%2Fhr,precipitation_probability,visibility,humidity,sunrise,sunset,weather_code'.format(latitude, longitude)
		get_daily = executor.submit(functions.getURL, url, cc_headers, flask_app)
		
		try:
			cc_current_obj = get_current.result()
		except:
			flask_app.logger.error('Exception occurred during cc_current_obj API call: {}'.format(sys.exc_info()[0]))
			cc_current_obj = None
		#  If this request failed, return an empty dictionary
		if not cc_current_obj:
			if input_dictionary:
				return input_dictionary
			else:
				return False
		
		try:
			cc_minutely_obj = get_minutely.result()
		except:
			flask_app.logger.error('Exception occurred during cc_minutely_obj API call: {}'.format(sys.exc_info()[0]))
			cc_minutely_obj = None
		#  If this request failed, return an empty dictionary
		if not cc_minutely_obj:
			if input_dictionary:
				return input_dictionary
			else:
				return False
		
		try:
			cc_hourly_obj = get_hourly.result()
		except:
			flask_app.logger.error('Exception occurred during cc_hourly_obj API call: {}'.format(sys.exc_info()[0]))
			cc_hourly_obj = None
		#  If this request failed, return an empty dictionary
		if not cc_hourly_obj:
			if input_dictionary:
				return input_dictionary
			else:
				return False
		
		try:
			cc_daily_obj = get_daily.result()
		except:
			flask_app.logger.error('Exception occurred during cc_daily_obj API call: {}'.format(sys.exc_info()[0]))
			cc_daily_obj = None
		#  If this request failed, return an empty dictionary
		if not cc_daily_obj:
			if input_dictionary:
				return input_dictionary
			else:
				return False

	#  Use the input dictionary or build a new one if we didn't get one
	if input_dictionary:
		output = input_dictionary
	else:
		#  Create the output JSON structure
		tf = TimezoneFinder()
		output = {
			'latitude': latitude,
			'longitude': longitude,
			#  Climacell does not provide the timezone
			'timezone': tf.timezone_at(lat=latitude, lng=longitude),
			'currently': {},
			'minutely': {},
			'hourly': {},
			'daily': {},
			#  Climacell does not provide alerts to free accounts
			#'alerts': [],    
			'flags': {
				'sources': [],
				'units': 'us'
			}
		}

		#  Calculate the timezone's offset from UTC in hours and add that
		#  to the output
		tz_now = datetime.datetime.now(pytz.timezone(output['timezone']))
		output['offset'] = tz_now.utcoffset().total_seconds() / 3600

	#--------------------------   C u r r e n t l y   --------------------------#

	#  Populate the output dictionary with the current observations
	if cc_current_obj:
		output['currently'] = {
			'time': functions.getKeyValue(cc_current_obj, ['observation_time', 'value'], lambda x: int(_epochTime(x))),
			'summary': functions.getKeyValue(cc_current_obj, ['weather_code', 'value'], lambda x: _mapClimacellWeatherCode(x)),
			'icon': functions.getKeyValue(cc_current_obj, ['weather_code', 'value'], lambda x: _mapIcons(x, flask_app)),
			#'nearestStormDistance': None,
			'precipIntensity': functions.getKeyValue(cc_current_obj, ['precipitation', 'value']),
			#'precipIntensityError': None,
			#'precipProbability': None,
			'precipType': functions.getKeyValue(cc_current_obj, ['precipitation_type', 'value'], lambda x: None if x == 'none' else x),
			'temperature': functions.getKeyValue(cc_current_obj, ['temp', 'value']),
			'apparentTemperature': functions.getKeyValue(cc_current_obj, ['feels_like', 'value']),
			'dewPoint': functions.getKeyValue(cc_current_obj, ['dewpoint', 'value']),
			'humidity': functions.getKeyValue(cc_current_obj, ['humidity', 'value'], lambda x: round(x / 100)),
			'pressure': functions.getKeyValue(cc_current_obj, ['baro_pressure', 'value']),
			'windSpeed': functions.getKeyValue(cc_current_obj, ['wind_speed', 'value']),
			'windGust': functions.getKeyValue(cc_current_obj, ['wind_gust', 'value']),
			'windBearing': functions.getKeyValue(cc_current_obj, ['wind_direction', 'value']),
			'cloudCover': functions.getKeyValue(cc_current_obj, ['cloud_cover', 'value'], lambda x: round(x / 100)),
			#'uvIndex': None,
			'visibility': functions.getKeyValue(cc_current_obj, ['visibility', 'value']),
			'ozone': functions.getKeyValue(cc_current_obj, ['o3', 'value']),
		}

	#---------------------------   M i n u t e l y   ---------------------------#	
	
	#  Add the minutely data from Climacell to the output dictionary
	if cc_minutely_obj:
		minutely_data = functions.getKeyValue(output, ['minutely', 'data'])
		
		#  If we already have minutely data, we won't change it.  We  only
		#  use our data when there isn't anything already in place.
		if not minutely_data or len(minutely_data) == 0:
			minutely_data = []
			for minute in cc_minutely_obj:
				minutely_data.append({
					'time': _epochTime(minute['observation_time']['value']),
					'precipIntensity': functions.getKeyValue(minute, ['precipitation', 'value']),
					#  Climacell doesn't provide these next two elements
					#  in their minute-by-minute forecast
					'precipIntesityError': None,
					'precipProbability': None,
					'precipType': functions.getKeyValue(minute, ['precipitation_type', 'value'], lambda x: None if x == 'none' else x)
				})
		
			output['minutely'] = {
				'summary': None,
				'icon': None,
				'data': minutely_data
			}
		
	#-----------------------------   H o u r l y   -----------------------------#	
	
	#  Add the hourly data from Climacell to the output dictionary
	if cc_hourly_obj:
		hourly_data = functions.getKeyValue(output, ['hourly', 'data'])
		
		#  If there's no hourly data then create an hourly data array
		#  with just a timestamp for each day
		if not hourly_data or len(hourly_data) == 0:
			hourly_data = []
			timestamp = int(datetime.datetime.combine(datetime.date.today(),datetime.time(datetime.datetime.now().hour)).timestamp())
			for timestamp in range(timestamp + (timestamp + (3600 * 48)), 3600):
				hourly_data.append({
					'time': int(timestamp)
				})

		#  Add the Climacell data for each day
		for i in range(len(hourly_data)):
			hour = hourly_data[i]
			cc_hour = cc_hourly_obj[i]
			if hour['time'] == _epochTime(cc_hour['observation_time']['value']):
				hourly_data[i] = {
					'time': hour['time'],
					'summary': functions.getKeyValue(cc_hour, ['weather_code', 'value'], lambda x: _mapClimacellWeatherCode(x)),
					'icon': functions.getKeyValue(cc_hour, ['weather_code', 'value'], lambda x: _mapIcons(x, flask_app)),
					#'nearestStormDistance': None,
					'precipIntensity': functions.getKeyValue(cc_hour, ['precipitation', 'value']),
					#'precipIntensityError': None,
					'precipProbability': functions.getKeyValue(cc_hour, ['precipitation_probability', 'value'], lambda x: round(x / 100, 2)),
					'precipType': functions.getKeyValue(cc_hour, ['precipitation_type', 'value'], lambda x: None if x == 'none' else x),
					'temperature': functions.getKeyValue(cc_hour, ['temp', 'value']),
					'apparentTemperature': functions.getKeyValue(cc_hour, ['feels_like', 'value']),
					'dewPoint': functions.getKeyValue(cc_hour, ['dewpoint', 'value']),
					'humidity': functions.getKeyValue(cc_hour, ['humidity', 'value'], lambda x: round(x / 100, 2)),
					'pressure': functions.getKeyValue(cc_hour, ['baro_pressure', 'value']),
					'windSpeed': functions.getKeyValue(cc_hour, ['wind_speed', 'value']),
					'windGust': functions.getKeyValue(cc_hour, ['wind_gust', 'value']),
					'windBearing': functions.getKeyValue(cc_hour, ['wind_direction', 'value']),
					'cloudCover': functions.getKeyValue(cc_hour, ['cloud_cover', 'value'], lambda x: round(x / 100, 2)),
					#'uvIndex': None,
					'visibility': functions.getKeyValue(cc_hour, ['visibility', 'value']),
					'ozone': functions.getKeyValue(cc_hour, ['o3', 'value'])
				}

			#  Use data from the first hour as the summary values for this
			#  section and the minutely section
			output['hourly']['summary'] = hourly_data[0]['summary']
			output['hourly']['icon'] = hourly_data[0]['icon']
			output['minutely']['summary'] = hourly_data[0]['summary']
			output['minutely']['icon'] = hourly_data[0]['icon']
		
		#  Put the hourly data into the output dictionary
		output['hourly']['data'] = hourly_data

	#------------------------------   D a i l y   ------------------------------#

	#  Add the daily data from Climacell to the output directory
	if cc_daily_obj:
		daily_data = functions.getKeyValue(output, ['daily', 'data'])
		
		#  If there's no daily data then create a daily data array
		#  with just a timestamp for each day
		if not daily_data or len(daily_data) == 0:
			daily_data = []
			d = datetime.datetime.utcnow()
			timestamp = int(datetime.datetime(d.year, d.month, d.day, 0, 0, 0, tzinfo=datetime.timezone.utc).timestamp())
			for timestamp in range(timestamp + (timestamp + (86400 * 8)), 86400):
				daily_data.append({
					'time': int(timestamp)
				})

		#  If there are less than 8 days in the array, add the missing
		#  days with just a timestamp value
		if len(daily_data) < 8:
			timestamp = daily_data[len(daily_data) - 1]['time']
			for i in range(8 - len(daily_data)):
				timestamp = timestamp + 86400
				daily_data.append({
					'time': timestamp
				})
				
		#  Align the dates in the two arrays
		ctr = 0
		for i in range(len(cc_daily_obj)):
			if _dailyEpochTime(cc_daily_obj[ctr]['observation_time']['value']) < daily_data[0]['time']:
				ctr = ctr + 1
				
		#  Update the data for each day
		for i in range(len(daily_data)):
			day = daily_data[i]
			cc_day = cc_daily_obj[ctr]
			daily_data[i] = {
				'time': day['time'],
				'summary': functions.getKeyValue(cc_day, ['weather_code', 'value'], lambda x: _mapClimacellWeatherCode(x)),
				'icon': functions.getKeyValue(cc_day, ['weather_code', 'value'], lambda x: _mapIcons(x, flask_app)),
				#'nearestStormDistance': None,
				'sunriseTime': functions.getKeyValue(cc_day, ['sunrise', 'value'], lambda x: round(isodate.parse_datetime(x).timestamp())),
				'sunsetTime': functions.getKeyValue(cc_day, ['sunset', 'value'], lambda x: round(isodate.parse_datetime(x).timestamp())),
				#  Climacell provides text moon phase names and we want
				#  the fractional part of the lunation number instead
				#  so we'll calculate this outselves using Astral
				'moonPhase': round(moon.phase(datetime.datetime.utcfromtimestamp(day['time'])) / 27.99, 2),
				'precipIntensity': functions.getKeyValue(cc_day, ['precipitation', 0, 'max', 'value']),
				'precipIntensityMax': functions.getKeyValue(cc_day, ['precipitation', 0, 'max', 'value']),
				'precipIntensityMaxTime': functions.getKeyValue(cc_day, ['precipitation', 'observation_time'], lambda x: int(isodate.parse_datetime(x).timestamp())),
				'precipProbability': functions.getKeyValue(cc_day, ['precipitation_probability', 'value']),
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
				'pressure': None,
				#  Climacell does not provide, using data from input array, if any
				'windSpeed': functions.getKeyValue(day, ['windSpeed']),
				'windGust': None,
				'windGustTime': None,
				#  Climacell does not provide, using data from input array, if any
				'windBearing': functions.getKeyValue(day, ['windBearing']),
				#  Climacell does not provide, using data from input array, if any
				'cloudCover': functions.getKeyValue(day, ['cloudCover']),
				#'uvIndex': None,
				#'uvIndexTime', None,
				#  Climacell does not provide, using data from input array, if any
				'visibility': functions.getKeyValue(day, ['visibility']),
				#'ozone': None,
				'temperatureMin': None,
				'temperatureMinTime': None,
				'temperatureMax': None,
				'temperatureMaxTime': None,
				'apparentTemperatureMin': None,
				'apparentTemperatureMinTime': None,
				'apparentTemperatureMax': None,
				'apparentTemperatureMaxTime': None
			}

			#  Get min and max temperatures from the Climacell data array and plug them in
			for t in cc_day['temp']:
				if 'min' in t:
					daily_data[i]['temperatureLow'] = t['min']['value'] 
					daily_data[i]['temperatureLowTime'] = int(isodate.parse_datetime(t['observation_time']).timestamp())
					daily_data[i]['temperatureMin'] = t['min']['value'] 
					daily_data[i]['temperatureMinTime'] = int(isodate.parse_datetime(t['observation_time']).timestamp())
				if 'max' in t:
					daily_data[i]['temperatureHigh'] = t['max']['value'] 
					daily_data[i]['temperatureHighTime'] = int(isodate.parse_datetime(t['observation_time']).timestamp())
					daily_data[i]['temperatureMax'] = t['max']['value'] 
					daily_data[i]['temperatureMaxTime'] = int(isodate.parse_datetime(t['observation_time']).timestamp())
			for t in cc_day['feels_like']:
				if 'min' in t:
					daily_data[i]['apparentTemperatureLow'] = t['min']['value'] 
					daily_data[i]['apparentTemperatureLowTime'] = int(isodate.parse_datetime(t['observation_time']).timestamp())
					daily_data[i]['apparentTemperatureMin'] = t['min']['value'] 
					daily_data[i]['apparentTemperatureMinTime'] = int(isodate.parse_datetime(t['observation_time']).timestamp())
				if 'max' in t:
					daily_data[i]['apparentTemperatureHigh'] = t['max']['value'] 
					daily_data[i]['apparentTemperatureHighTime'] = int(isodate.parse_datetime(t['observation_time']).timestamp())
					daily_data[i]['apparentTemperatureMax'] = t['max']['value'] 
					daily_data[i]['apparentTemperatureMaxTime'] = int(isodate.parse_datetime(t['observation_time']).timestamp())

			#  Get the average of the min and max humidity and use
			#  that for the daily value
			for t in cc_day['humidity']:
				total = 0
				if 'min' in t:
					total = total + t['min']['value'] 
				if 'max' in t:
					total = total + t['max']['value'] 
				daily_data[i]['humidity'] = round(total / len(cc_day['humidity']), 2)
				
			#  Get the average of the min and max barometric pressure
			#  and use that for the daily value
			for t in cc_day['baro_pressure']:
				total = 0
				if 'min' in t:
					total = total + t['min']['value'] 
				if 'max' in t:
					total = total + t['max']['value'] 
				daily_data[i]['pressure'] = round(total / len(cc_day['baro_pressure']), 2)
				
			#  Get the max wind speed and plug that in as windGust
			for t in cc_day['wind_speed']:
				if 'max' in t:
					daily_data[i]['windGust'] = t['max']['value'] 
					daily_data[i]['windGustTime'] = int(isodate.parse_datetime(t['observation_time']).timestamp())

			ctr = ctr + 1
			
		#  Use data from the first day as the summary values for this
		#  section
		output['daily']['summary'] = daily_data[0]['summary']
		output['daily']['icon'] = daily_data[0]['icon']
		
		#  Put the daily data into the output dictionary
		output['daily']['data'] = daily_data
	
	#-----------------------------   A l e r t s   -----------------------------#
	
	'''
	Climacell's alerts are a proprietary messaging system, not weather
	alerts. If the input data structure included NOAA weather alerts,
	those will be passed through untouched.
	'''

	#  Add a source flag for this source
	sources = []
	if functions.getKeyValue(input_dictionary, ['flags', 'sources']):
		for source in functions.getKeyValue(input_dictionary, ['flags', 'sources']):
			sources.append(source)
	sources.append('climacell')
	output['flags']['sources'] = sources
	
	return output
