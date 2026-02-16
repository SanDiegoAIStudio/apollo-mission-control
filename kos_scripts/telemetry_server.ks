// telemetry_server.ks — KSP-side kOS script
// Runs on the vessel and provides telemetry dumps on request.
//
// This script exposes a TELEMETRY_DUMP function that serializes
// current vessel state as JSON for the Mission Control bridge.

@LAZYGLOBAL OFF.

PRINT "=== APOLLO MISSION CONTROL TELEMETRY SERVER ===".
PRINT "Initializing telemetry export...".

// Determine mission phase based on vessel situation
FUNCTION get_phase {
    IF SHIP:STATUS = "PRELAUNCH" { RETURN "prelaunch". }
    IF SHIP:STATUS = "LANDED" {
        IF SHIP:BODY:NAME = "Mun" { RETURN "surface". }
        RETURN "prelaunch".
    }
    IF SHIP:STATUS = "FLYING" { RETURN "ascent". }
    IF SHIP:STATUS = "SUB_ORBITAL" { RETURN "ascent". }
    IF SHIP:STATUS = "ORBITING" {
        IF SHIP:BODY:NAME = "Mun" { RETURN "loi". }
        RETURN "orbit".
    }
    RETURN "orbit".
}

// Build a JSON string of engine data
FUNCTION engines_json {
    LOCAL result IS "".
    LOCAL eng_list IS LIST().
    LIST ENGINES IN eng_list.
    LOCAL first IS TRUE.
    result IS result + "[".
    FOR eng IN eng_list {
        IF NOT first { SET result TO result + ",". }
        SET result TO result + "{".
        SET result TO result + CHAR(34) + "engine_name" + CHAR(34) + ":" + CHAR(34) + eng:NAME + CHAR(34) + ",".
        SET result TO result + CHAR(34) + "active" + CHAR(34) + ":" + eng:IGNITION + ",".
        SET result TO result + CHAR(34) + "thrust" + CHAR(34) + ":" + eng:THRUST + ",".
        SET result TO result + CHAR(34) + "max_thrust" + CHAR(34) + ":" + eng:MAXTHRUST + ",".
        SET result TO result + CHAR(34) + "isp" + CHAR(34) + ":" + eng:ISP + ",".
        SET result TO result + CHAR(34) + "fuel_flow" + CHAR(34) + ":" + eng:FUELFLOW + ",".
        SET result TO result + CHAR(34) + "flameout" + CHAR(34) + ":" + eng:FLAMEOUT.
        SET result TO result + "}".
        SET first TO FALSE.
    }
    SET result TO result + "]".
    RETURN result.
}

// Build JSON for resources
FUNCTION resources_json {
    LOCAL result IS "[".
    LOCAL first IS TRUE.
    FOR res IN SHIP:RESOURCES {
        IF NOT first { SET result TO result + ",". }
        SET result TO result + "{".
        SET result TO result + CHAR(34) + "name" + CHAR(34) + ":" + CHAR(34) + res:NAME + CHAR(34) + ",".
        SET result TO result + CHAR(34) + "amount" + CHAR(34) + ":" + res:AMOUNT + ",".
        SET result TO result + CHAR(34) + "max_amount" + CHAR(34) + ":" + res:CAPACITY.
        SET result TO result + "}".
        SET first TO FALSE.
    }
    SET result TO result + "]".
    RETURN result.
}

// Main telemetry dump function
FUNCTION TELEMETRY_DUMP {
    LOCAL ec IS SHIP:ELECTRICCHARGE.
    LOCAL result IS "{".

    // Mission elapsed time
    SET result TO result + CHAR(34) + "met" + CHAR(34) + ":" + MISSIONTIME + ",".
    SET result TO result + CHAR(34) + "phase" + CHAR(34) + ":" + CHAR(34) + get_phase() + CHAR(34) + ",".

    // Vessel state
    SET result TO result + CHAR(34) + "vessel" + CHAR(34) + ":{".
    SET result TO result + CHAR(34) + "mass" + CHAR(34) + ":" + SHIP:MASS * 1000 + ",".
    SET result TO result + CHAR(34) + "pos_x" + CHAR(34) + ":" + SHIP:POSITION:X + ",".
    SET result TO result + CHAR(34) + "pos_y" + CHAR(34) + ":" + SHIP:POSITION:Y + ",".
    SET result TO result + CHAR(34) + "pos_z" + CHAR(34) + ":" + SHIP:POSITION:Z + ",".
    SET result TO result + CHAR(34) + "vel_x" + CHAR(34) + ":" + SHIP:VELOCITY:ORBIT:X + ",".
    SET result TO result + CHAR(34) + "vel_y" + CHAR(34) + ":" + SHIP:VELOCITY:ORBIT:Y + ",".
    SET result TO result + CHAR(34) + "vel_z" + CHAR(34) + ":" + SHIP:VELOCITY:ORBIT:Z + ",".
    SET result TO result + CHAR(34) + "altitude" + CHAR(34) + ":" + SHIP:ALTITUDE + ",".
    SET result TO result + CHAR(34) + "heading" + CHAR(34) + ":" + SHIP:HEADING + ",".
    SET result TO result + CHAR(34) + "pitch" + CHAR(34) + ":" + 0 + ",".
    SET result TO result + CHAR(34) + "roll" + CHAR(34) + ":" + 0 + ",".
    SET result TO result + CHAR(34) + "throttle" + CHAR(34) + ":" + THROTTLE + ",".
    SET result TO result + CHAR(34) + "stage" + CHAR(34) + ":" + STAGE:NUMBER + ",".
    SET result TO result + CHAR(34) + "situation" + CHAR(34) + ":" + CHAR(34) + SHIP:STATUS + CHAR(34).
    SET result TO result + "},".

    // Orbital elements
    SET result TO result + CHAR(34) + "orbital" + CHAR(34) + ":{".
    SET result TO result + CHAR(34) + "body" + CHAR(34) + ":" + CHAR(34) + SHIP:BODY:NAME + CHAR(34) + ",".
    SET result TO result + CHAR(34) + "apoapsis" + CHAR(34) + ":" + SHIP:ORBIT:APOAPSIS + ",".
    SET result TO result + CHAR(34) + "periapsis" + CHAR(34) + ":" + SHIP:ORBIT:PERIAPSIS + ",".
    SET result TO result + CHAR(34) + "inclination" + CHAR(34) + ":" + SHIP:ORBIT:INCLINATION + ",".
    SET result TO result + CHAR(34) + "eccentricity" + CHAR(34) + ":" + SHIP:ORBIT:ECCENTRICITY + ",".
    SET result TO result + CHAR(34) + "sma" + CHAR(34) + ":" + SHIP:ORBIT:SEMIMAJORAXIS + ",".
    SET result TO result + CHAR(34) + "eta_ap" + CHAR(34) + ":" + ETA:APOAPSIS + ",".
    SET result TO result + CHAR(34) + "eta_pe" + CHAR(34) + ":" + ETA:PERIAPSIS + ",".
    SET result TO result + CHAR(34) + "velocity" + CHAR(34) + ":" + SHIP:VELOCITY:ORBIT:MAG.
    SET result TO result + "},".

    // Engines
    SET result TO result + CHAR(34) + "engines" + CHAR(34) + ":" + engines_json() + ",".

    // Resources
    SET result TO result + CHAR(34) + "resources" + CHAR(34) + ":" + resources_json() + ",".

    // Power
    SET result TO result + CHAR(34) + "power" + CHAR(34) + ":{".
    SET result TO result + CHAR(34) + "electric_charge" + CHAR(34) + ":{".
    SET result TO result + CHAR(34) + "name" + CHAR(34) + ":" + CHAR(34) + "ElectricCharge" + CHAR(34) + ",".
    SET result TO result + CHAR(34) + "amount" + CHAR(34) + ":" + ec:AMOUNT + ",".
    SET result TO result + CHAR(34) + "max_amount" + CHAR(34) + ":" + ec:CAPACITY.
    SET result TO result + "},".
    SET result TO result + CHAR(34) + "charge_rate" + CHAR(34) + ":0,".
    SET result TO result + CHAR(34) + "solar_deployed" + CHAR(34) + ":false,".
    SET result TO result + CHAR(34) + "fuel_cells" + CHAR(34) + ":false".
    SET result TO result + "},".

    // Comms and crew
    SET result TO result + CHAR(34) + "comms" + CHAR(34) + ":" + SHIP:CONNECTION:ISCONNECTED + ",".
    SET result TO result + CHAR(34) + "crew" + CHAR(34) + ":" + SHIP:CREW:LENGTH.

    SET result TO result + "}".

    PRINT result.
}

PRINT "Telemetry server ready. Call TELEMETRY_DUMP() for data.".
PRINT "Waiting for Mission Control connection...".
