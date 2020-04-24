<?php

// Borrowed from Darryl Hein's post on stackoverflow:
// https://stackoverflow.com/questions/10053358/measuring-the-distance-between-two-coordinates-in-php

/**
 * Calculate the great-circle distance between two points, with the
 * Vincenty formula.
 * @param float $latitudeFrom Latitude of start point in [deg decimal]
 * @param float $longitudeFrom Longitude of start point in [deg decimal]
 * @param float $latitudeTo Latitude of target point in [deg decimal]
 * @param float $longitudeTo Longitude of target point in [deg decimal]
 * @return float Distance between points in miles
 */
function vincentyGreatCircleDistance($latitudeFrom, $longitudeFrom, $latitudeTo, $longitudeTo) {
	$earthRadius = 6371000;	// metres

	// convert from degrees to radians
	$latFrom = deg2rad($latitudeFrom);
	$lonFrom = deg2rad($longitudeFrom);
	$latTo = deg2rad($latitudeTo);
	$lonTo = deg2rad($longitudeTo);

	$lonDelta = $lonTo - $lonFrom;
	$a = pow(cos($latTo) * sin($lonDelta), 2) +	pow(cos($latFrom) * sin($latTo) - sin($latFrom) * cos($latTo) * cos($lonDelta), 2);
	$b = sin($latFrom) * sin($latTo) + cos($latFrom) * cos($latTo) * cos($lonDelta);

	$angle = atan2(sqrt($a), $b);
	return $angle * $earthRadius / 1609.34;  // metres/1609.34 = miles
}

?>
